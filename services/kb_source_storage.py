from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

from services.http_client import get_async_http_client
from services.image_upload import ImageUploadError, delete_worker_file, upload_worker_file
from services.kb_limits import MAX_KB_UPLOAD_BYTES, PayloadTooLargeError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredKBSource:
    url: str
    key: str
    sha256: str
    size_bytes: int
    content_type: str


def _kb_folder() -> str:
    return os.getenv("KB_WORKER_FOLDER", "knowledgebase").strip()


def content_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


async def store_kb_source(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str],
) -> StoredKBSource:
    result = await upload_worker_file(
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        folder=_kb_folder(),
    )
    return StoredKBSource(
        url=result.url,
        key=result.key,
        sha256=content_sha256(file_bytes),
        size_bytes=len(file_bytes),
        content_type=content_type or "application/octet-stream",
    )


async def download_kb_source(url: str, max_bytes: int = MAX_KB_UPLOAD_BYTES) -> bytes:
    if not url:
        raise ValueError("Stored knowledge source URL is missing")

    client = await get_async_http_client()
    async with client.stream("GET", url, timeout=30.0) as response:
        response.raise_for_status()
        size = 0
        chunks: list[bytes] = []
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise PayloadTooLargeError(f"Stored source is too large. Maximum size is {max_bytes // (1024 * 1024)}MB.")
            chunks.append(chunk)
    return b"".join(chunks)


async def delete_kb_source(key: Optional[str]) -> bool:
    if not key:
        return False
    try:
        return await delete_worker_file(key)
    except ImageUploadError:
        logger.warning("kb_source_delete_failed key=%s", key, exc_info=True)
        return False
