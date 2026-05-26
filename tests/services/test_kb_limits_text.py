import pytest

from services import kb_limits


def test_enforce_text_limit_exact_boundary():
    text = "x" * 4

    size = kb_limits.enforce_text_limit(text, max_bytes=4)

    assert size == 4, (
        "Expected enforce_text_limit to allow text at exact byte boundary"
    )


def test_enforce_text_limit_raises_on_multibyte():
    text = "\u2603"  # snowman is 3 bytes in UTF-8

    with pytest.raises(kb_limits.PayloadTooLargeError) as exc:
        kb_limits.enforce_text_limit(text, max_bytes=2)

    assert "Extracted text is too large" in str(exc.value), (
        "Expected error message when multibyte text exceeds limit"
    )
