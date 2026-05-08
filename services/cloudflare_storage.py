from __future__ import annotations

import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class WorkerUploadResult(BaseModel):
    success: bool
    url: str
    key: str


class WorkerUploadError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, response_text: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def _setting(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or default


async def upload_to_worker(
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    *,
    folder: str | None = None,
) -> WorkerUploadResult:
    worker_url = _setting("IMAGE_WORKER_URL") or _setting("CLOUDFLARE_WORKER_URL")
    api_key = _setting("IMAGE_WORKER_API_KEY") or _setting("CLOUDFLARE_WORKER_API_KEY")
    app_name = _setting("IMAGE_WORKER_APP_NAME", "helpdesk-ai")

    if not worker_url or not api_key:
        raise WorkerUploadError("Cloudflare worker upload service is not configured")

    files = {
        "file": (filename, file_bytes, content_type or "application/octet-stream"),
    }
    data = {
        "app": app_name,
        "folder": folder or _setting("IMAGE_WORKER_DOCUMENT_FOLDER", "knowledge-base"),
    }
    headers = {
        "x-api-key": api_key,
    }

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(worker_url, headers=headers, data=data, files=files)

    if response.status_code >= 400:
        response_preview = response.text[:500] if response.text else ""
        raise WorkerUploadError(
            f"Cloudflare worker upload failed with status {response.status_code}",
            status_code=response.status_code,
            response_text=response_preview,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise WorkerUploadError("Cloudflare worker returned invalid JSON") from exc

    if not payload.get("success") or not payload.get("url"):
        raise WorkerUploadError("Cloudflare worker did not return a valid upload URL")

    return WorkerUploadResult(
        success=bool(payload.get("success")),
        url=str(payload.get("url")),
        key=str(payload.get("key", "")),
    )


async def upload_avatar_image(
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
) -> WorkerUploadResult:
    return await upload_to_worker(
        file_bytes,
        filename,
        content_type,
        folder=_setting("IMAGE_WORKER_AVATAR_FOLDER", "avatars"),
    )


async def upload_knowledge_file(
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
) -> WorkerUploadResult:
    return await upload_to_worker(
        file_bytes,
        filename,
        content_type,
        folder=_setting("IMAGE_WORKER_DOCUMENT_FOLDER", "knowledge-base"),
    )


async def upload_extracted_text(
    text: str,
    filename: str,
) -> WorkerUploadResult:
    return await upload_to_worker(
        text.encode("utf-8"),
        filename,
        "text/plain; charset=utf-8",
        folder=_setting("IMAGE_WORKER_EXTRACTED_FOLDER", "knowledge-extracted"),
    )


async def download_text_from_url(url: str) -> str:
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
    response.raise_for_status()
    return response.text
