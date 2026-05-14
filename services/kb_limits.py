import os
from typing import Protocol


class AsyncUploadFile(Protocol):
    async def read(self, size: int = -1) -> bytes:
        ...


class PayloadTooLargeError(ValueError):
    pass


MAX_KB_UPLOAD_BYTES = int(os.getenv("MAX_KB_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_KB_TEXT_BYTES = int(os.getenv("MAX_KB_TEXT_BYTES", str(5 * 1024 * 1024)))
READ_CHUNK_BYTES = 1024 * 1024


async def read_upload_limited(file: AsyncUploadFile, max_bytes: int = MAX_KB_UPLOAD_BYTES) -> bytes:
    size = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise PayloadTooLargeError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)}MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def enforce_text_limit(text: str, max_bytes: int = MAX_KB_TEXT_BYTES) -> int:
    size = len(text.encode("utf-8"))
    if size > max_bytes:
        raise PayloadTooLargeError(
            f"Extracted text is too large. Maximum extracted text size is {max_bytes // (1024 * 1024)}MB."
        )
    return size
