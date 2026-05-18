import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/db")


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, ttl):
        self.expirations[key] = ttl


class PerformanceRemediationTests(unittest.IsolatedAsyncioTestCase):
    async def test_widget_rate_limit_uses_redis_counter(self):
        from api.agents import widget_deployment

        redis = FakeRedis()
        original_get_redis = widget_deployment.get_async_redis
        widget_deployment.get_async_redis = lambda: redis
        request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.10"))
        try:
            for _ in range(widget_deployment.RATE_LIMIT_MAX_REQUESTS):
                await widget_deployment._check_rate_limit("deployment", "visitor", request)
            with self.assertRaises(HTTPException) as exc:
                await widget_deployment._check_rate_limit("deployment", "visitor", request)
            self.assertEqual(exc.exception.status_code, 429)
        finally:
            widget_deployment.get_async_redis = original_get_redis

    async def test_auth_cache_round_trips_through_redis(self):
        from services import supabase_auth

        class SyncRedis:
            def __init__(self):
                self.values = {}

            def setex(self, key, ttl, value):
                self.values[key] = value

            def get(self, key):
                return self.values.get(key)

            def delete(self, key):
                self.values.pop(key, None)

        class Db:
            def get(self, model, user_id):
                return SimpleNamespace(id=user_id, email="user@example.com")

        redis = SyncRedis()
        original_get_redis = supabase_auth.get_sync_redis
        supabase_auth.get_sync_redis = lambda: redis
        try:
            token = "not.a.jwt"
            user = SimpleNamespace(id=42)
            supabase_auth._cache_user(token, user)
            cached = supabase_auth._get_cached_user(Db(), token)
            self.assertEqual(cached.id, 42)
        finally:
            supabase_auth.get_sync_redis = original_get_redis

    async def test_celery_enqueue_spools_text_and_dispatches_task(self):
        from services import ingest_queue, ingest_tasks

        calls = []

        class FakeTask:
            @staticmethod
            def delay(job_id, spool_path):
                calls.append((job_id, spool_path))
                return SimpleNamespace(id="task-1")

        original_task = ingest_tasks.process_kb_ingest_job_task
        original_spool = ingest_queue._SPOOL_DIR
        ingest_tasks.process_kb_ingest_job_task = FakeTask()
        with tempfile.TemporaryDirectory() as tmp_dir:
            ingest_queue._SPOOL_DIR = Path(tmp_dir)
            try:
                self.assertTrue(ingest_queue.enqueue_kb_ingest("job-1", "hello world"))
                self.assertEqual(calls[0][0], "job-1")
                self.assertEqual(Path(calls[0][1]).read_text(encoding="utf-8"), "hello world")
            finally:
                ingest_queue._SPOOL_DIR = original_spool
                ingest_tasks.process_kb_ingest_job_task = original_task


class FileParserTests(unittest.TestCase):
    def test_pdf_extraction_uses_joined_page_text(self):
        from services import file_parser

        class Page:
            def __init__(self, value):
                self.value = value

            def extract_text(self):
                return self.value

        class Reader:
            def __init__(self, file):
                self.pages = [Page("one"), Page("two")]

        original_reader = file_parser.PdfReader
        file_parser.PdfReader = Reader
        try:
            self.assertEqual(file_parser.extract_text_from_pdf_file(object()), "one two")
        finally:
            file_parser.PdfReader = original_reader


if __name__ == "__main__":
    unittest.main()
