import os
import uuid
from typing import Callable, Iterable, Iterator, List, Optional

import httpx
from litellm import completion
from sqlalchemy.orm import Session

from services.vector_store import format_context, search as milvus_search, upsert_texts
from utils.env import get_secret

JINA_EMBED_MODEL = os.getenv("JINA_EMBED_MODEL", "jina-embeddings-v5-text-small")
JINA_EMBEDDING_URL = os.getenv("JINA_EMBEDDING_URL", "https://api.jina.ai/v1/embeddings")
CONCISE_RUNTIME_INSTRUCTION = """### Response Style
- Keep answers concise and easy to scan.
- Prefer 1-3 short paragraphs.
- Use bullets only when they genuinely make the answer clearer.
- Ask one brief clarifying question if needed.
- Do not include long explanations unless the user explicitly asks for detail."""


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


def embed_texts(texts: Iterable[str], task: str = "retrieval.passage") -> List[List[float]]:
    values = list(texts)
    if not values:
        return []
    api_key = get_secret("JINAAI_API_KEY", prefixes=("jina_",)) or get_secret("JINA_API_KEY", prefixes=("jina_",))
    if not api_key:
        raise RuntimeError("JINAAI_API_KEY is not set")
    payload = {
        "model": JINA_EMBED_MODEL,
        "task": task,
        "normalized": True,
        "input": values,
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            JINA_EMBEDDING_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    data = response.json().get("data", [])
    return [item["embedding"] for item in data]


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
        vectors = embed_texts(batch, task="retrieval.passage")
        ids = [str(uuid.uuid4()) for _ in batch]
        upsert_texts(namespace, kb_id, agent_id, batch, vectors, ids=ids)
        if on_batch:
            on_batch(end, total_chunks)

    return total_chunks


def retrieve_context(db: Session, namespace: str, agent_id: str, query: str, top_k: int = 4) -> str:
    qvec = embed_texts([query], task="retrieval.query")[0]
    return format_context(milvus_search(namespace, qvec, top_k=top_k))


def build_messages(
    system_prompt: str,
    context: str,
    message: str,
    history: Optional[list[dict[str, str]]] = None,
) -> list[dict[str, str]]:
    content = f"{system_prompt}\n\n{CONCISE_RUNTIME_INSTRUCTION}".strip()
    if context:
        content = f"{content}\n\nRelevant context:\n<context>\n{context}\n</context>"
    messages = [{"role": "system", "content": content}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": f"<user_query>\n{message}\n</user_query>"})
    return messages


def generate_answer(model: str, messages: list[dict[str, str]]) -> str:
    if model.startswith("groq/"):
        groq_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    response = completion(model=model, messages=messages, temperature=0.2, max_tokens=700)
    return response.choices[0].message.content.strip()


def stream_answer(model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    if model.startswith("groq/"):
        groq_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    for chunk in completion(model=model, messages=messages, temperature=0.2, max_tokens=700, stream=True):
        delta = chunk.choices[0].delta
        content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
        if content:
            yield content
