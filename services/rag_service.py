import os
import uuid
from typing import Callable, Iterable, Iterator, List, Optional

from litellm import completion, embedding
from sqlalchemy.orm import Session

from services.vector_store import format_context, search as milvus_search, upsert_texts

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")


def chunk_text(text_value: str, size: int = 1000, overlap: int = 150) -> List[str]:
    cleaned = " ".join(text_value.split())
    chunks, start = [], 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        cut = cleaned.rfind(" ", start, end)
        if cut > start + size // 2:
            end = cut
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(end - overlap, end) if end >= len(cleaned) else max(end - overlap, start + 1)
    return chunks


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    values = list(texts)
    if not values:
        return []
    response = embedding(model=EMBED_MODEL, input=values)
    return [item["embedding"] if isinstance(item, dict) else item.embedding for item in response.data]


def _vector_literal(vector: List[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def index_kb_text(
    db: Session,
    user_id: int,
    agent_id: str,
    kb_id: str,
    namespace: str,
    text_value: str,
    batch_size: int = 32,
    on_batch: Optional[Callable[[int, int], None]] = None,
) -> int:
    chunks = chunk_text(text_value)
    total_chunks = len(chunks)
    if total_chunks == 0:
        return 0

    for start in range(0, total_chunks, batch_size):
        end = min(start + batch_size, total_chunks)
        batch = chunks[start:end]
        vectors = embed_texts(batch)
        ids = [str(uuid.uuid4()) for _ in batch]
        upsert_texts(namespace, kb_id, agent_id, batch, vectors, ids=ids)
        if on_batch:
            on_batch(end, total_chunks)

    return total_chunks


def retrieve_context(db: Session, namespace: str, agent_id: str, query: str, top_k: int = 4) -> str:
    qvec = embed_texts([query])[0]
    rows = db.execute(
        text(
            """
            WITH vector_ranked AS (
                SELECT id, content, row_number() OVER (ORDER BY embedding <=> CAST(:embedding AS vector)) AS rank
                FROM documents
                WHERE agent_id = CAST(:agent_id AS uuid)
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            ),
            keyword_ranked AS (
                SELECT id, content, row_number() OVER (ORDER BY similarity(content, :query) DESC) AS rank
                FROM documents
                WHERE agent_id = CAST(:agent_id AS uuid) AND content % :query
                ORDER BY similarity(content, :query) DESC
                LIMIT :limit
            ),
            fused AS (
                SELECT id, content, 1.0 / (60 + rank) AS score FROM vector_ranked
                UNION ALL
                SELECT id, content, 1.0 / (60 + rank) AS score FROM keyword_ranked
            )
            SELECT content, sum(score) AS rrf_score
            FROM fused
            GROUP BY id, content
            ORDER BY rrf_score DESC
            LIMIT :top_k
            """
        ),
        {"agent_id": agent_id, "embedding": _vector_literal(qvec), "query": query, "limit": top_k * 4, "top_k": top_k},
    ).all()
    if rows:
        return "\n\n".join(row.content for row in rows)
    return format_context(milvus_search(namespace, qvec, top_k=top_k))


def build_messages(system_prompt: str, context: str, message: str) -> list[dict[str, str]]:
    content = system_prompt
    if context:
        content = f"{content}\n\nRelevant context:\n{context}"
    return [{"role": "system", "content": content}, {"role": "user", "content": message}]


def generate_answer(model: str, messages: list[dict[str, str]]) -> str:
    response = completion(model=model, messages=messages, temperature=0.2)
    return response.choices[0].message.content.strip()


def stream_answer(model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    for chunk in completion(model=model, messages=messages, temperature=0.2, stream=True):
        delta = chunk.choices[0].delta
        content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
        if content:
            yield content
