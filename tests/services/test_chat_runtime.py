import pytest

from services import chat_runtime


class FakeQuery:
    def __init__(self, row):
        self._row = row
        self._filters = []

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._row


class FakeSession:
    def __init__(self, row):
        self._row = row

    def query(self, *_args, **_kwargs):
        return FakeQuery(self._row)


class DummyAgent:
    def __init__(self):
        self.id = "agent-1"
        self.user_id = 7
        self.name = "Agent"
        self.instructions = ""
        self.model = "groq/openai/gpt-oss-20b"


class DummyConfig:
    def __init__(self):
        self.retrieval_enabled = True
        self.retrieval_top_k = 5
        self.vector_store_namespace = "ns"


@pytest.mark.anyio
async def test_get_agent_runtime_returns_cached(monkeypatch):
    cached = {
        "id": "agent-1",
        "user_id": 7,
        "name": "Agent",
        "instructions": "Hi",
        "model": "groq/openai/gpt-oss-20b",
        "retrieval_enabled": True,
        "retrieval_top_k": 4,
        "vector_store_namespace": None,
    }

    async def fake_get_json(_key):
        return cached

    monkeypatch.setattr(chat_runtime, "aredis_get_json", fake_get_json)

    runtime = await chat_runtime.get_agent_runtime(db=FakeSession(None), agent_id="agent-1", user_id=7)

    assert runtime is not None, "Expected cached runtime to be returned"
    assert runtime.id == "agent-1", f"Expected runtime.id to be 'agent-1', got {runtime.id!r}"
    assert runtime.retrieval_top_k == 4, (
        "Expected cached retrieval_top_k to be preserved"
    )


@pytest.mark.anyio
async def test_get_agent_runtime_builds_from_db(monkeypatch):
    async def fake_get_json(_key):
        return None

    captured = {}

    async def fake_set_json(key, value, ttl):
        captured["key"] = key
        captured["value"] = value
        captured["ttl"] = ttl

    monkeypatch.setattr(chat_runtime, "aredis_get_json", fake_get_json)
    monkeypatch.setattr(chat_runtime, "aredis_set_json", fake_set_json)

    row = (DummyAgent(), DummyConfig())
    runtime = await chat_runtime.get_agent_runtime(db=FakeSession(row), agent_id="agent-1", user_id=7)

    assert runtime is not None, "Expected runtime to be built from db row"
    assert runtime.retrieval_top_k == 5, (
        "Expected retrieval_top_k to come from config when set"
    )
    assert captured["value"]["vector_store_namespace"] == "ns", (
        "Expected cached runtime to include vector store namespace"
    )


def test_invalidate_agent_runtime_deletes_cache(monkeypatch):
    captured = {}

    def fake_delete(key):
        captured["key"] = key

    monkeypatch.setattr(chat_runtime, "redis_delete", fake_delete)

    chat_runtime.invalidate_agent_runtime(agent_id="agent-1", user_id=7)

    assert captured["key"].endswith("chat:runtime:7:agent-1"), (
        "Expected invalidate_agent_runtime to target user-specific cache key"
    )
