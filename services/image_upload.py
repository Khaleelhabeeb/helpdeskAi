from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class ImageUploadResult:
    success: bool
    url: str
    key: str


class ImageUploadError(Exception):
    pass


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


async def upload_avatar_image(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str],
) -> ImageUploadResult:
    image_worker_url = _env("IMAGE_WORKER_URL")
    image_worker_api_key = _env("IMAGE_WORKER_API_KEY")
    image_worker_app_name = _env("IMAGE_WORKER_APP_NAME")
    image_worker_avatar_folder = _env("IMAGE_WORKER_AVATAR_FOLDER")

    if not image_worker_url or not image_worker_api_key:
        raise ImageUploadError("Image upload service is not configured")

    files = {
        "file": (filename, file_bytes, content_type or "application/octet-stream"),
    }
    data = {
        "app": image_worker_app_name,
        "folder": image_worker_avatar_folder,
    }
    headers = {
        "x-api-key": image_worker_api_key,
    }

    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            image_worker_url,
            headers=headers,
            data=data,
            files=files,
        )

    if response.status_code >= 400:
        raise ImageUploadError("Image worker upload failed")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ImageUploadError("Image worker returned invalid JSON") from exc

    if not payload.get("success") or not payload.get("url"):
        raise ImageUploadError("Image worker did not return a valid upload URL")

    return ImageUploadResult(
        success=bool(payload.get("success")),
        url=str(payload.get("url")),
        key=str(payload.get("key", "")),
    )
