import os

import pytest

from utils import env


def test_get_secret_returns_env_value_with_prefix_match(monkeypatch):
    env.get_secret.cache_clear()
    monkeypatch.setenv("API_KEY", "gsk_test_123")

    value = env.get_secret("API_KEY", prefixes=("gsk_",))

    assert value == "gsk_test_123", (
        "Expected get_secret to return the env var when prefix matches; "
        f"got {value!r}"
    )


def test_get_secret_reads_dotenv_when_env_missing(tmp_path, monkeypatch):
    env.get_secret.cache_clear()
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text("API_KEY='gsk_from_env'\n")

    value = env.get_secret("API_KEY", prefixes=("gsk_",))

    assert value == "gsk_from_env", (
        "Expected get_secret to read .env when env var is missing; "
        f"got {value!r}"
    )


def test_get_secret_ignores_commented_or_blank_lines(tmp_path, monkeypatch):
    env.get_secret.cache_clear()
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text("#API_KEY=ignored\nAPI_KEY=   \nAPI_KEY='gsk_real'\n")

    value = env.get_secret("API_KEY", prefixes=("gsk_",))

    assert value == "gsk_real", (
        "Expected get_secret to skip commented/blank lines and use valid value; "
        f"got {value!r}"
    )
