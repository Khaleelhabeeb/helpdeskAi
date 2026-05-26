import hashlib
import os
import re
import uuid
import anyio
import httpx
from typing import Callable, Iterable, Iterator, List, Optional, AsyncIterator

from sqlalchemy.orm import Session

from services.http_client import default_timeout, get_async_http_client
from services.redis_client import aredis_get_json, aredis_set_json, cache_key
from services.vector_store import format_context, search as milvus_search, upsert_texts
from utils.env import get_secret

JINA_EMBED_MODEL = os.getenv("JINA_EMBED_MODEL", "jina-embeddings-v5-text-small")
JINA_EMBEDDING_URL = os.getenv("JINA_EMBEDDING_URL", "https://api.jina.ai/v1/embeddings")
JINA_EMBED_MAX_CONCURRENCY = int(os.getenv("JINA_EMBED_MAX_CONCURRENCY", "4"))
LLM_STREAM_MAX_CONCURRENCY = int(os.getenv("LLM_STREAM_MAX_CONCURRENCY", "8"))
RAG_CONTEXT_CACHE_TTL_SECONDS = int(os.getenv("RAG_CONTEXT_CACHE_TTL_SECONDS", "180"))
RAG_RETRIEVAL_TIMEOUT_SECONDS = float(os.getenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", "2.5"))
_embed_semaphore = anyio.Semaphore(JINA_EMBED_MAX_CONCURRENCY)
_llm_semaphore = anyio.Semaphore(LLM_STREAM_MAX_CONCURRENCY)
CONCISE_RUNTIME_INSTRUCTION = """### Response Style
- Keep answers concise and easy to scan.
- Prefer 1-3 short paragraphs.
- Use bullets only when they genuinely make the answer clearer.
- Ask one brief clarifying question if needed.
- Do not include long explanations unless the user explicitly asks for detail."""


_MULTI_WS = re.compile(r"\s+")


def chunk_text(text_value: str, size: int = 1000, overlap: int = 150) -> List[str]:
    cleaned = _MULTI_WS.sub(" ", text_value).strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    text_len = len(cleaned)
    while start < text_len:
        end = min(start + size, text_len)
        if end < text_len:
            cut = cleaned.rfind(" ", start + 1, end)
            if cut > start + size // 2:
                end = cut
        chunks.append(cleaned[start:end])
        start = end - overlap if end < text_len else end
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
    with httpx.Client(timeout=default_timeout()) as client:
        response = client.post(
            JINA_EMBEDDING_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    data = response.json().get("data", [])
    return [item["embedding"] for item in data]


async def aembed_texts(texts: Iterable[str], task: str = "retrieval.passage") -> List[List[float]]:
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
    async with _embed_semaphore:
        client = await get_async_http_client()
        response = await client.post(
            JINA_EMBEDDING_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    data = response.json().get("data", [])
    return [item["embedding"] for item in data]


async def aindex_kb_text(
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
        vectors = await aembed_texts(batch, task="retrieval.passage")
        ids = [str(uuid.uuid4()) for _ in batch]
        # Upsert is blocking, run in thread
        await anyio.to_thread.run_sync(
            lambda: upsert_texts(namespace, kb_id, agent_id, batch, vectors, ids=ids)
        )
        if on_batch:
            on_batch(end, total_chunks)

    return total_chunks


def retrieve_context(db: Session, namespace: str, agent_id: str, query: str, top_k: int = 4) -> str:
    qvec = embed_texts([query], task="retrieval.query")[0]
    return format_context(milvus_search(namespace, qvec, top_k=top_k))


async def aretrieve_context(db: Session, namespace: str, agent_id: str, query: str, top_k: int = 4) -> str:
    if should_skip_retrieval(query):
        return ""
    query_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    cache_id = cache_key("rag", "context", namespace, top_k, query_hash)
    cached_context = await aredis_get_json(cache_id)
    if isinstance(cached_context, str):
        return cached_context

    with anyio.fail_after(RAG_RETRIEVAL_TIMEOUT_SECONDS):
        qvecs = await aembed_texts([query], task="retrieval.query")
        if not qvecs:
            return ""
        results = await anyio.to_thread.run_sync(lambda: milvus_search(namespace, qvecs[0], top_k=top_k))
        context = format_context(results)
    if context:
        await aredis_set_json(cache_id, context, RAG_CONTEXT_CACHE_TTL_SECONDS)
    return context


def should_skip_retrieval(query: str) -> bool:
    normalized = " ".join(query.lower().strip().split())
    if not normalized:
        return True
    quick_phrases = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "ok",
        "okay",
    }
    if normalized in quick_phrases:
        return True
    return len(normalized.split()) <= 3 and normalized.rstrip("?!") in quick_phrases


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
    from litellm import completion

    if model.startswith("groq/"):
        groq_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    response = completion(model=model, messages=messages, temperature=0.2, max_tokens=700)
    return response.choices[0].message.content.strip()


def stream_answer(model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    from litellm import completion

    if model.startswith("groq/"):
        groq_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    for chunk in completion(model=model, messages=messages, temperature=0.2, max_tokens=700, stream=True):
        delta = chunk.choices[0].delta
        content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
        if content:
            yield content


async def astream_answer(model: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
    from litellm import acompletion

    if model.startswith("groq/"):
        groq_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    async with _llm_semaphore:
        response = await acompletion(model=model, messages=messages, temperature=0.2, max_tokens=700, stream=True)
        async for chunk in response:
            delta = chunk.choices[0].delta
            content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
            if content:
                yield content
