import pytest

from services import kb_limits


class FakeAsyncFile:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


@pytest.mark.anyio
async def test_read_upload_limited_returns_combined_bytes():
    file_obj = FakeAsyncFile([b"abc", b"def", b""])

    result = await kb_limits.read_upload_limited(file_obj, max_bytes=10)

    assert result == b"abcdef", (
        "Expected read_upload_limited to join all chunks when under limit; "
        f"got {result!r}"
    )


@pytest.mark.anyio
async def test_read_upload_limited_raises_on_size_limit():
    file_obj = FakeAsyncFile([b"12345", b"67890"])

    with pytest.raises(kb_limits.PayloadTooLargeError) as exc:
        await kb_limits.read_upload_limited(file_obj, max_bytes=7)

    assert "Maximum size is" in str(exc.value), (
        "Expected PayloadTooLargeError message to include size hint; "
        f"got {exc.value!r}"
    )


def test_enforce_text_limit_returns_byte_size():
    text = "hello"

    size = kb_limits.enforce_text_limit(text, max_bytes=10)

    assert size == len(text.encode("utf-8")), (
        "Expected enforce_text_limit to return UTF-8 byte length; "
        f"got {size}"
    )


def test_enforce_text_limit_raises_on_size_limit():
    text = "x" * 5

    with pytest.raises(kb_limits.PayloadTooLargeError) as exc:
        kb_limits.enforce_text_limit(text, max_bytes=3)

    assert "Maximum extracted text size" in str(exc.value), (
        "Expected PayloadTooLargeError message to mention extracted text limit; "
        f"got {exc.value!r}"
    )
