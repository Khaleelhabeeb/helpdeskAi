import pytest

from utils import jwt, security


def test_verify_token_is_deprecated():
    with pytest.raises(RuntimeError) as exc:
        jwt.verify_token("token")

    assert "Supabase Auth" in str(exc.value), (
        "Expected verify_token to indicate Supabase Auth replacement; "
        f"got {exc.value!r}"
    )


def test_hash_password_is_deprecated():
    with pytest.raises(RuntimeError) as exc:
        security.hash_password("secret")

    assert "Supabase Auth" in str(exc.value), (
        "Expected hash_password to indicate Supabase Auth replacement; "
        f"got {exc.value!r}"
    )
