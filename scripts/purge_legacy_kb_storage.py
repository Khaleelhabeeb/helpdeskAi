"""One-off purge of legacy KB objects from the upload worker (R2).

Background: file/text knowledge sources used to be uploaded to the image
worker for later retraining. That is gone — originals are never stored now.
This script deletes the leftover remote objects, then NULLs the legacy
columns so the drop-column migration applies cleanly.

Order of operations:
  1. `uv run python scripts/purge_legacy_kb_storage.py`            # dry run
  2. `uv run python scripts/purge_legacy_kb_storage.py --apply`    # delete
  3. `alembic upgrade head`                                        # drops columns

Safe to re-run: already-purged rows (NULL key, or worker 404/405) are
skipped. Exits non-zero if any delete fails, leaving those rows untouched
for a retry.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purge_legacy_kb_storage")


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _worker_config() -> dict:
    return {
        "url": os.getenv("IMAGE_WORKER_URL", "").strip(),
        "delete_url": os.getenv("IMAGE_WORKER_DELETE_URL", "").strip(),
        "api_key": os.getenv("IMAGE_WORKER_API_KEY", "").strip(),
        "app": os.getenv("IMAGE_WORKER_APP_NAME", "").strip(),
        "method": os.getenv("IMAGE_WORKER_DELETE_METHOD", "").strip() or "DELETE",
    }


def delete_remote_object(client, cfg: dict, key: str) -> str:
    """Returns 'deleted' or 'gone' (confirmed absent). Raises otherwise.

    NOTE: 404 means the object is confirmed absent. 405 is NOT success — it
    means the worker has no delete endpoint at all, in which case objects
    must be removed via the Cloudflare R2 dashboard (or `wrangler r2 object
    delete`) and this script cannot do it.
    """
    import httpx

    target = cfg["delete_url"] or cfg["url"]
    try:
        response = client.request(
            cfg["method"],
            target,
            headers={"x-api-key": cfg["api_key"]},
            json={"key": key, "app": cfg["app"]},
            timeout=30.0,
        )
    except Exception as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    if response.status_code == 404:
        return "gone"
    if response.status_code == 405:
        raise RuntimeError(
            "worker has no delete endpoint (405). Delete via the Cloudflare R2 "
            "dashboard: bucket behind this worker, prefix helpdeskai/knowledgebase/"
        )
    if response.status_code >= 400:
        raise RuntimeError(f"worker said {response.status_code}: {response.text[:200]}")
    return "deleted"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually delete. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=0, help="Only process N rows (0 = all).")
    args = parser.parse_args()

    _load_env()
    cfg = _worker_config()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        logger.error("DATABASE_URL is not set")
        return 2

    import httpx
    from sqlalchemy import create_engine, text

    if args.apply and (not cfg["url"] or not cfg["api_key"]):
        logger.error("IMAGE_WORKER_URL / IMAGE_WORKER_API_KEY are required to delete")
        return 2

    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source_storage_key FROM knowledge_bases "
                "WHERE source_storage_key IS NOT NULL"
            )
        ).all()
    if args.limit:
        rows = rows[: args.limit]
    logger.info("rows with legacy storage key: %d", len(rows))
    if not rows:
        return 0

    if not args.apply:
        logger.info("DRY RUN — nothing deleted. Re-run with --apply. Sample:")
        for row in rows[:10]:
            logger.info("  kb_id=%s key=%s", row[0], row[1])
        return 0

    deleted = gone = failed = 0
    failures: list[str] = []
    with httpx.Client(timeout=30.0) as client:
        with engine.begin() as conn:
            for kb_id, key in rows:
                try:
                    outcome = delete_remote_object(client, cfg, key)
                except Exception as exc:
                    failed += 1
                    failures.append(f"kb_id={kb_id} key={key}: {exc}")
                    logger.warning("delete failed kb_id=%s key=%s err=%s", kb_id, key, exc)
                    continue
                if outcome == "deleted":
                    deleted += 1
                else:
                    gone += 1
                conn.execute(
                    text(
                        "UPDATE knowledge_bases SET source_storage_url = NULL, "
                        "source_storage_key = NULL WHERE id = :kb_id"
                    ),
                    {"kb_id": kb_id},
                )
    logger.info("deleted=%d already_gone=%d failed=%d", deleted, gone, failed)
    for line in failures[:20]:
        logger.warning("FAILED %s", line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
