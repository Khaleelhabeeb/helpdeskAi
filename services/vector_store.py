import logging
import os
from typing import Any, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from dotenv import load_dotenv

if TYPE_CHECKING:
    from pymilvus import MilvusClient

load_dotenv()
logger = logging.getLogger(__name__)

MILVUS_COLLECTION = os.getenv("JINA_MILVUS_COLLECTION", "documents_jina")
VECTOR_DIM = int(os.getenv("JINA_EMBEDDING_DIMENSION", "1024"))

MILVUS_TIMEOUT_SECONDS = float(os.getenv("MILVUS_TIMEOUT_SECONDS", "10"))
RAG_CONTEXT_MAX_CHARS = int(os.getenv("RAG_CONTEXT_MAX_CHARS", "3500"))

_client: Optional["MilvusClient"] = None


def get_milvus_client() -> "MilvusClient":
    global _client
    if _client is None:
        from pymilvus import MilvusClient

        uri = os.getenv("ZILLIZ_URI") or os.getenv("MILVUS_URI")
        token = os.getenv("ZILLIZ_TOKEN") or os.getenv("MILVUS_TOKEN")
        if not uri or not token:
            raise RuntimeError("ZILLIZ_URI and ZILLIZ_TOKEN must be set")
        uri = uri.strip()
        if uri and not urlparse(uri).scheme and not uri.endswith(".db"):
            uri = f"https://{uri}"
        _client = MilvusClient(uri=uri, token=token, timeout=MILVUS_TIMEOUT_SECONDS)
    return _client


def ensure_collection() -> None:
    client = get_milvus_client()
    if client.has_collection(MILVUS_COLLECTION, timeout=MILVUS_TIMEOUT_SECONDS):
        return
    logger.info("creating_milvus_collection collection=%s dimension=%s", MILVUS_COLLECTION, VECTOR_DIM)
    client.create_collection(
        collection_name=MILVUS_COLLECTION,
        dimension=VECTOR_DIM,
        primary_field_name="id",
        id_type="string",
        vector_field_name="embedding",
        metric_type="COSINE",
        auto_id=False,
        max_length=64,
        enable_dynamic_field=True,
        timeout=MILVUS_TIMEOUT_SECONDS,
    )


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def upsert_texts(
    namespace: str,
    kb_id: str,
    agent_id: str,
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
) -> int:
    ensure_collection()
    rows: List[dict[str, Any]] = []
    for i, text in enumerate(texts):
        metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
        rows.append(
            {
                "id": ids[i] if ids else f"{kb_id}:{i}",
                "embedding": embeddings[i],
                "namespace": namespace,
                "kb_id": kb_id,
                "agent_id": agent_id,
                "chunk_index": i,
                "text": text,
                **metadata,
            }
        )
    if rows:
        get_milvus_client().upsert(collection_name=MILVUS_COLLECTION, data=rows, timeout=MILVUS_TIMEOUT_SECONDS)
    return len(rows)


def search(namespace: str, query_vector: List[float], top_k: int = 4) -> List[tuple[str, float]]:
    ensure_collection()
    results = get_milvus_client().search(
        collection_name=MILVUS_COLLECTION,
        data=[query_vector],
        filter=f'namespace == "{_quote(namespace)}"',
        limit=top_k,
        output_fields=["text"],
        anns_field="embedding",
        timeout=MILVUS_TIMEOUT_SECONDS,
    )
    hits: List[tuple[str, float]] = []
    for hit in results[0] if results else []:
        entity = hit.get("entity", hit)
        hits.append((entity.get("text", ""), float(hit.get("distance", hit.get("score", 0.0)))))
    return hits


def format_context(results: List[tuple[str, float]], max_chars: int = RAG_CONTEXT_MAX_CHARS) -> str:
    parts: List[str] = []
    total = 0
    for text, _ in results:
        if text and total + len(text) + 2 <= max_chars:
            parts.append(text)
            total += len(text) + 2
    return "\n\n".join(parts)


def delete_for_kb(namespace: str, kb_id: str) -> int:
    ensure_collection()
    get_milvus_client().delete(
        collection_name=MILVUS_COLLECTION,
        filter=f'namespace == "{_quote(namespace)}" and kb_id == "{_quote(kb_id)}"',
        timeout=MILVUS_TIMEOUT_SECONDS,
    )
    return 1


def delete_namespace(namespace: str) -> int:
    ensure_collection()
    get_milvus_client().delete(
        collection_name=MILVUS_COLLECTION,
        filter=f'namespace == "{_quote(namespace)}"',
        timeout=MILVUS_TIMEOUT_SECONDS,
    )
    return 1
