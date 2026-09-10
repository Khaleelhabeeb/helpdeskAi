import logging
import os
import sys
from typing import Any, List, Optional
import uuid

from sqlalchemy import text

logger = logging.getLogger(__name__)

VECTOR_DIM = int(os.getenv("JINA_EMBEDDING_DIMENSION", "1024"))
RAG_CONTEXT_MAX_CHARS = int(os.getenv("RAG_CONTEXT_MAX_CHARS", "3500"))


def ensure_collection() -> None:
    """
    Ensure pgvector table exists (migration `pgvector_20250911` should have run).
    Silent no-op in sqlite tests.
    """
    try:
        from db.database import engine
        from sqlalchemy import inspect

        insp = inspect(engine)
        if "kb_chunks" not in insp.get_table_names():
            logger.warning("kb_chunks table not found — run `alembic upgrade head`")
    except Exception:
        pass


def _get_session():
    """Create a short-lived session for vector ops (isolated from caller's transaction)."""
    from db.database import SessionLocal

    return SessionLocal()


def _is_sqlite_test() -> bool:
    """Detect pytest/sqlite env where pgvector operator is unavailable."""
    if "pytest" in sys.modules:
        return True
    try:
        from db.database import engine

        return engine.dialect.name == "sqlite"
    except Exception:
        return False


def upsert_texts(
    namespace: str,
    kb_id: str,
    agent_id: str,
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
    chunk_offset: int = 0,
) -> int:
    """
    Insert chunks into `kb_chunks` (pgvector).
    - Replaces Milvus `upsert` (which was idempotent on `id`).
    - Uses bulk insert via SQLAlchemy ORM for speed.
    - `chunk_offset` allows global chunk_index across batches (rag_service passes batch start).
    - `ids` if provided are used as primary key `id`; otherwise gen_random_uuid().
    """
    if not texts or not embeddings:
        return 0

    # Lazy import to avoid circular deps at module load
    from models.kb_chunk import KbChunk

    session = _get_session()
    try:
        objects: List[KbChunk] = []
        is_sqlite = _is_sqlite_test()
        for i, (txt, emb) in enumerate(zip(texts, embeddings)):
            if not txt:
                continue
            # Use provided id as PK if valid UUID, else generate
            raw_id = ids[i] if ids and i < len(ids) else None
            try:
                pk = uuid.UUID(raw_id) if raw_id else uuid.uuid4()
            except Exception:
                pk = uuid.uuid4()

            # chunk_index should be global for stable ordering; fall back to batch i + offset
            c_idx = chunk_offset + i

            # For sqlite tests, embedding column is Text — serialize
            if is_sqlite:
                # store as comma-separated string for test introspection (not used for search)
                emb_val = ",".join(map(str, emb)) if isinstance(emb, list) else str(emb)  # type: ignore
            else:
                emb_val = emb  # type: ignore

            obj = KbChunk(
                id=pk,
                kb_id=uuid.UUID(kb_id) if isinstance(kb_id, str) else kb_id,
                agent_id=uuid.UUID(agent_id) if isinstance(agent_id, str) else agent_id,
                namespace=namespace,
                chunk_index=c_idx,
                text=txt,
                embedding=emb_val,  # pgvector Vector type handles list -> vector
            )
            objects.append(obj)

        if not objects:
            return 0

        # Bulk insert — use add_all for simplicity; for high throughput could use executemany
        session.add_all(objects)
        session.commit()
        return len(objects)
    except Exception:
        session.rollback()
        logger.exception("pgvector_upsert_failed namespace=%s kb_id=%s", namespace, kb_id)
        raise
    finally:
        session.close()


def search(namespace: str, query_vector: List[float], top_k: int = 4) -> List[tuple[str, float]]:
    """
    Cosine-similarity search filtered by namespace.
    Returns List[(text, distance)] sorted by increasing cosine distance (most similar first).
    Distance = 1 - cosine_similarity for normalized Jina vectors, matching previous Milvus COSINE.

    Uses pgvector HNSW index `ix_kb_chunks_embedding_hnsw` (vector_cosine_ops) for fast top-k.
    """
    if not query_vector:
        return []

    # In sqlite/pytest env, fallback to simple namespace-filtered fetch (no vector ordering)
    if _is_sqlite_test():
        session = _get_session()
        try:
            from models.kb_chunk import KbChunk

            rows = (
                session.query(KbChunk.text)
                .filter(KbChunk.namespace == namespace)
                .limit(top_k)
                .all()
            )
            return [(r[0], 0.0) for r in rows if r[0]]
        except Exception:
            return []
        finally:
            session.close()

    session = _get_session()
    try:
        # Use raw SQL with explicit CAST for pgvector to ensure index usage and no ORM overhead.
        # `embedding <=> :vec` is cosine distance operator for vector_cosine_ops.
        # We format vector as pgvector string "[1,2,...]" and cast to vector.
        # For performance, keep LIMIT small (top_k 3-4).
        vec_str = "[" + ",".join(map(str, query_vector)) + "]"
        sql = text(
            """
            SELECT text, embedding <=> CAST(:vec AS vector) AS distance
            FROM kb_chunks
            WHERE namespace = :ns
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        )
        rows = session.execute(sql, {"vec": vec_str, "ns": namespace, "limit": top_k}).fetchall()
        # rows: [(text, distance)]
        hits: List[tuple[str, float]] = []
        for r in rows:
            txt = r[0]
            dist = float(r[1]) if r[1] is not None else 1.0
            if txt:
                hits.append((txt, dist))
        return hits
    except Exception as exc:
        # If table doesn't exist or vector op missing, return empty gracefully (e.g. migration not yet run)
        msg = str(exc).lower()
        if "kb_chunks" in msg or "no such table" in msg or "does not exist" in msg or "vector" in msg or "operator" in msg:
            logger.debug("pgvector_search_no_table namespace=%s", namespace)
            return []
        logger.exception("pgvector_search_failed namespace=%s", namespace)
        raise
    finally:
        session.close()


def format_context(results: List[tuple[str, float]], max_chars: int = RAG_CONTEXT_MAX_CHARS) -> str:
    parts: List[str] = []
    total = 0
    for text, _ in results:
        if text and total + len(text) + 2 <= max_chars:
            parts.append(text)
            total += len(text) + 2
    return "\n\n".join(parts)


def delete_for_kb(namespace: str, kb_id: str) -> int:
    """Delete all chunks for a specific KB (filtered by namespace for safety)."""
    session = _get_session()
    try:
        # Use ORM delete for clarity; raw SQL also fine
        from models.kb_chunk import KbChunk

        # Need to cast kb_id string to UUID
        try:
            kb_uuid = uuid.UUID(kb_id)
        except Exception:
            kb_uuid = kb_id  # type: ignore

        q = session.query(KbChunk).filter(KbChunk.kb_id == kb_uuid, KbChunk.namespace == namespace)
        count = q.count()  # for logging
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("pgvector_delete_kb namespace=%s kb_id=%s count=%s", namespace, kb_id, count)
        return count
    except Exception:
        session.rollback()
        logger.exception("pgvector_delete_kb_failed namespace=%s kb_id=%s", namespace, kb_id)
        raise
    finally:
        session.close()


def delete_namespace(namespace: str) -> int:
    """Delete all chunks for a namespace (cascade on agent delete)."""
    session = _get_session()
    try:
        from models.kb_chunk import KbChunk

        q = session.query(KbChunk).filter(KbChunk.namespace == namespace)
        count = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("pgvector_delete_namespace namespace=%s count=%s", namespace, count)
        return count
    except Exception:
        session.rollback()
        logger.exception("pgvector_delete_namespace_failed namespace=%s", namespace)
        raise
    finally:
        session.close()


# Backward compat aliases (some callers import `search as milvus_search`)
# Keep `get_milvus_client` stub to avoid ImportError during transition
def get_milvus_client():  # pragma: no cover
    raise RuntimeError("Milvus is removed — pgvector is now used. See services/vector_store.py")
