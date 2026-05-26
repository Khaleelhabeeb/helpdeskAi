from datetime import datetime

from services import storage_quota


class FakeUsage:
    def __init__(self):
        self.total_files = 2
        self.total_size_bytes = 1024 * 1024
        self.total_chunks = 4
        self.last_updated = datetime(2024, 1, 1)


class FakeUser:
    def __init__(self):
        self.id = 1
        self.user_type = "free"


def test_get_storage_stats_returns_expected_shape(monkeypatch):
    def fake_get_or_create(_db, _user_id):
        return FakeUsage()

    monkeypatch.setattr(storage_quota, "get_or_create_storage_usage", fake_get_or_create)

    user = FakeUser()
    stats = storage_quota.get_storage_stats(db=None, user=user)

    assert stats["user_type"] == "free", (
        "Expected stats to include user_type"
    )
    assert stats["total_files"] == 2, (
        "Expected stats to include total_files"
    )
    assert stats["total_size_mb"] == 1.0, (
        "Expected total_size_mb to be derived from bytes"
    )
    assert stats["total_chunks"] == 4, (
        "Expected stats to include total_chunks"
    )
