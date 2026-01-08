import os
import uuid
from typing import List, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "helpdesk_docs")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Lazy-loaded embedders to avoid startup overhead
_doc_embedder = None
_query_embedder = None


def _get_doc_embedder():
    global _doc_embedder
    if _doc_embedder is None:
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY must be set")
        _doc_embedder = GoogleGenerativeAIEmbeddings(
            model=GEMINI_EMBED_MODEL,
            task_type="RETRIEVAL_DOCUMENT",
            google_api_key=GOOGLE_API_KEY,
        )
    return _doc_embedder


def _get_query_embedder():
    global _query_embedder
    if _query_embedder is None:
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY must be set")
        _query_embedder = GoogleGenerativeAIEmbeddings(
            model=GEMINI_EMBED_MODEL,
            task_type="RETRIEVAL_QUERY",
            google_api_key=GOOGLE_API_KEY,
        )
    return _query_embedder


def get_qdrant_client() -> QdrantClient:
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set")
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ensure_collection(client: QdrantClient, vector_size: int = 3072) -> None:
    existing = client.get_collections()
    names = [c.name for c in existing.collections]
    if QDRANT_COLLECTION not in names:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )
    # Ensure payload indexes for filterable fields
    for field in ("namespace", "kb_id", "agent_id"):
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass


def _build_payload(namespace: str, kb_id: str, agent_id: str, text: str, metadata: Optional[dict]) -> dict:
    payload = {
        "namespace": namespace,
        "kb_id": kb_id,
        "agent_id": agent_id,
        "text": text,
    }
    if metadata:
        payload.update(metadata)
    return payload


def upsert_texts(namespace: str, kb_id: str, agent_id: str, texts: List[str], metadatas: Optional[List[dict]] = None) -> int:
    client = get_qdrant_client()
    ensure_collection(client)

    vectors = _get_doc_embedder().embed_documents(texts)
    points = []
    for i, vec in enumerate(vectors):
        pid = str(uuid.uuid4())
        metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
        payload = _build_payload(namespace, kb_id, agent_id, texts[i], metadata)
        points.append(qmodels.PointStruct(id=pid, vector=vec, payload=payload))

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return len(points)


essential_payload_fields = ["namespace", "kb_id", "agent_id", "text"]

def search(namespace: str, query: str, top_k: int = 4) -> List[Tuple[str, float]]:
    client = get_qdrant_client()
    ensure_collection(client)

    qvec = _get_query_embedder().embed_query(query)
    flt = qmodels.Filter(
        must=[qmodels.FieldCondition(key="namespace", match=qmodels.MatchValue(value=namespace))]
    )
    res = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=qvec,
        limit=top_k,
        query_filter=flt,
        with_payload=True,
        with_vectors=False,
    )
    results: List[Tuple[str, float]] = []
    for r in res:
        text = (r.payload or {}).get("text", "")
        results.append((text, r.score))
    return results


def format_context(results: List[Tuple[str, float]], max_chars: int = 6000) -> str:
    parts: List[str] = []
    total = 0
    for text, _ in results:
        if not text:
            continue
        if total + len(text) + 2 > max_chars:
            break
        parts.append(text)
        total += len(text) + 2
    return "\n\n".join(parts)


def delete_for_kb(namespace: str, kb_id: str) -> int:
    client = get_qdrant_client()
    ensure_collection(client)
    flt = qmodels.Filter(
        must=[
            qmodels.FieldCondition(key="namespace", match=qmodels.MatchValue(value=namespace)),
            qmodels.FieldCondition(key="kb_id", match=qmodels.MatchValue(value=kb_id)),
        ]
    )
    res = client.delete(collection_name=QDRANT_COLLECTION, points_selector=qmodels.FilterSelector(filter=flt))
    return getattr(res, "status", 0)  # status may not be numeric; returned for debugging


def delete_namespace(namespace: str) -> int:
    client = get_qdrant_client()
    ensure_collection(client)
    flt = qmodels.Filter(
        must=[qmodels.FieldCondition(key="namespace", match=qmodels.MatchValue(value=namespace))]
    )
    res = client.delete(collection_name=QDRANT_COLLECTION, points_selector=qmodels.FilterSelector(filter=flt))
    return getattr(res, "status", 0)
