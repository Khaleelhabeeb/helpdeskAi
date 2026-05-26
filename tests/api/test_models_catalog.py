import pytest

from api import models as model_catalog


def test_model_label_known_alias():
    label = model_catalog.model_label("groq/openai/gpt-oss-20b")

    assert label == "GPT OSS 20B", (
        "Expected model_label to use alias for GPT OSS 20B; "
        f"got {label!r}"
    )


def test_model_label_fallback_formatting():
    label = model_catalog.model_label("groq/foo/bar-baz")

    assert label == "Foo / Bar Baz", (
        "Expected model_label to format unknown models with title casing; "
        f"got {label!r}"
    )


def test_model_logo_provider_detection():
    assert model_catalog.model_logo("groq/meta-llama/llama-4-scout") == "meta", (
        "Expected llama models to map to meta logo"
    )
    assert model_catalog.model_logo("groq/gemma2-9b-it") == "google", (
        "Expected gemma models to map to google logo"
    )
    assert model_catalog.model_logo("groq/unknown") == "groq", (
        "Expected unknown models to map to groq logo"
    )


@pytest.mark.anyio
async def test_available_models_returns_cached_when_present(monkeypatch):
    cached_models = [{"id": "groq/x", "label": "X", "provider": "groq", "logo": "groq", "locked": False}]

    async def fake_get_json(_key):
        return cached_models

    monkeypatch.setattr(model_catalog, "aredis_get_json", fake_get_json)

    result = await model_catalog.available_models(user=None)

    assert result == {"models": cached_models}, (
        "Expected available_models to return cached models when present; "
        f"got {result!r}"
    )


@pytest.mark.anyio
async def test_available_models_falls_back_to_static_list(monkeypatch):
    async def fake_get_json(_key):
        return None

    async def fake_set_json(_key, _value, _ttl):
        return None

    monkeypatch.setattr(model_catalog, "aredis_get_json", fake_get_json)
    monkeypatch.setattr(model_catalog, "aredis_set_json", fake_set_json)
    monkeypatch.setattr(model_catalog, "get_secret", lambda *_args, **_kwargs: None)

    result = await model_catalog.available_models(user=None)

    models = result.get("models")
    expected_ids = sorted(set(model_catalog.FALLBACK_GROQ_MODELS))
    actual_ids = [item.get("id") for item in models]

    assert actual_ids == expected_ids, (
        "Expected available_models to return sorted fallback model ids when no API key; "
        f"got {actual_ids!r}"
    )
    assert all(item.get("provider") == "groq" for item in models), (
        "Expected fallback models to have provider='groq'"
    )
    assert all(item.get("locked") is False for item in models), (
        "Expected fallback models to be unlocked"
    )
