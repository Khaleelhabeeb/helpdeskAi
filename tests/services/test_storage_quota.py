from types import SimpleNamespace

from services import storage_quota


class FakeSession:
    def __init__(self):
        self._usage = None
        self._committed = False

    def query(self, _model):
        return self

    def filter(self, _expr):
        return self

    def first(self):
        return self._usage

    def add(self, usage):
        self._usage = usage

    def commit(self):
        self._committed = True

    def refresh(self, _usage):
        return None


class FakeUsage:
    def __init__(self, user_id):
        self.user_id = user_id
        self.total_files = 0
        self.total_size_bytes = 0
        self.total_chunks = 0
        self.last_updated = None


def test_get_or_create_storage_usage_creates_when_missing(monkeypatch):
    class FakeUsageModel:
        user_id = "user_id"

        def __init__(self, user_id):
            self.user_id = user_id
            self.total_files = 0
            self.total_size_bytes = 0
            self.total_chunks = 0
            self.last_updated = None

    monkeypatch.setattr(storage_quota.models, "UserStorageUsage", FakeUsageModel)

    db = FakeSession()
    usage = storage_quota.get_or_create_storage_usage(db, user_id=1)

    assert usage.user_id == 1, (
        "Expected storage usage to be created for missing user"
    )
    assert db._committed is True, (
        "Expected storage usage creation to commit the session"
    )


def test_increment_storage_usage_updates_counters(monkeypatch):
    usage = FakeUsage(user_id=1)

    def fake_get_or_create(_db, _user_id):
        return usage

    monkeypatch.setattr(storage_quota, "get_or_create_storage_usage", fake_get_or_create)

    db = FakeSession()
    storage_quota.increment_storage_usage(db, user_id=1, file_size_bytes=10, chunk_count=2)

    assert usage.total_files == 1, (
        "Expected increment_storage_usage to increase total_files"
    )
    assert usage.total_size_bytes == 10, (
        "Expected increment_storage_usage to increase total_size_bytes"
    )
    assert usage.total_chunks == 2, (
        "Expected increment_storage_usage to increase total_chunks"
    )
