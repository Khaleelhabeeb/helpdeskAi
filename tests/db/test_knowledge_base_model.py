import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models import KnowledgeBase, KBIngestJob
from models.enums import KBSourceType, KBStatus, JobState


class TestKnowledgeBaseModel:
    def test_create_knowledge_base(self, db_session, agent):
        kb = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.upload_pdf,
            source_uri="s3://bucket/file.pdf",
            title="Product Manual",
            status=KBStatus.pending,
            original_filename="manual.pdf",
            source_content_type="application/pdf",
            file_size_bytes=102400,
        )
        db_session.add(kb)
        db_session.commit()
        db_session.refresh(kb)

        assert kb.id is not None
        assert kb.agent_id == agent.id
        assert kb.source_type == KBSourceType.upload_pdf
        assert kb.title == "Product Manual"
        assert kb.status == KBStatus.pending
        assert kb.original_filename == "manual.pdf"
        assert kb.file_size_bytes == 102400
        assert kb.created_at is not None
        assert kb.updated_at is not None

    def test_knowledge_base_defaults(self, db_session, agent):
        kb = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.text,
        )
        db_session.add(kb)
        db_session.commit()
        db_session.refresh(kb)

        assert kb.status == KBStatus.pending
        assert kb.title is None
        assert kb.source_uri is None

    def test_knowledge_base_agent_relationship(self, db_session, agent, knowledge_base):
        fetched = db_session.get(KnowledgeBase, knowledge_base.id)
        assert fetched.agent_id == agent.id
        assert fetched.agent is not None
        assert fetched.agent.name == agent.name

    def test_knowledge_base_jobs_relationship(self, db_session, knowledge_base):
        job1 = KBIngestJob(
            kb_id=knowledge_base.id,
            state=JobState.queued,
            total_chunks=100,
        )
        job2 = KBIngestJob(
            kb_id=knowledge_base.id,
            state=JobState.running,
            total_chunks=100,
            processed_chunks=50,
        )
        db_session.add_all([job1, job2])
        db_session.commit()

        fetched = db_session.get(KnowledgeBase, knowledge_base.id)
        assert len(fetched.jobs) == 2
        states = {j.state for j in fetched.jobs}
        assert states == {JobState.queued, JobState.running}

    def test_knowledge_base_jobs_cascade_delete(self, db_session, knowledge_base):
        job = KBIngestJob(kb_id=knowledge_base.id, state=JobState.queued)
        db_session.add(job)
        db_session.commit()

        job_id = job.id
        db_session.delete(knowledge_base)
        db_session.commit()

        remaining = db_session.get(KBIngestJob, job_id)
        assert remaining is None

    def test_knowledge_base_has_stored_source_property(self, db_session, agent):
        kb1 = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.upload_pdf,
            source_storage_key="uploads/abc.pdf",
        )
        kb2 = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.url,
            source_storage_url="https://example.com/doc.pdf",
        )
        kb3 = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.text,
        )
        db_session.add_all([kb1, kb2, kb3])
        db_session.commit()

        assert kb1.has_stored_source is True
        assert kb2.has_stored_source is True
        assert kb3.has_stored_source is False

    def test_knowledge_base_enums_stored_as_strings(self, db_session, agent):
        kb = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.upload_txt,
            status=KBStatus.ready,
        )
        db_session.add(kb)
        db_session.commit()

        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb.id)
        result = db_session.execute(stmt).scalar_one()
        assert result.source_type == KBSourceType.upload_txt
        assert result.status == KBStatus.ready


class TestKBIngestJobModel:
    def test_create_ingest_job(self, db_session, knowledge_base):
        job = KBIngestJob(
            kb_id=knowledge_base.id,
            state=JobState.running,
            total_chunks=50,
            processed_chunks=25,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.id is not None
        assert job.kb_id == knowledge_base.id
        assert job.state == JobState.running
        assert job.total_chunks == 50
        assert job.processed_chunks == 25
        assert job.error is None
        assert job.created_at is not None

    def test_ingest_job_defaults(self, db_session, knowledge_base):
        job = KBIngestJob(kb_id=knowledge_base.id)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.state == JobState.queued
        assert job.total_chunks is None
        assert job.processed_chunks is None

    def test_ingest_job_kb_relationship(self, db_session, knowledge_base):
        job = KBIngestJob(kb_id=knowledge_base.id, state=JobState.succeeded)
        db_session.add(job)
        db_session.commit()

        fetched = db_session.get(KBIngestJob, job.id)
        assert fetched.kb_id == knowledge_base.id
        assert fetched.kb is not None
        assert fetched.kb.title == knowledge_base.title

    def test_ingest_job_error_field(self, db_session, knowledge_base):
        job = KBIngestJob(
            kb_id=knowledge_base.id,
            state=JobState.failed,
            error="Failed to extract text from PDF",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.state == JobState.failed
        assert job.error == "Failed to extract text from PDF"

    def test_ingest_job_progress_tracking(self, db_session, knowledge_base):
        job = KBIngestJob(
            kb_id=knowledge_base.id,
            state=JobState.running,
            total_chunks=100,
            processed_chunks=0,
        )
        db_session.add(job)
        db_session.commit()

        job.processed_chunks = 50
        db_session.commit()
        assert job.processed_chunks == 50

        job.processed_chunks = 100
        job.state = JobState.succeeded
        db_session.commit()
        assert job.processed_chunks == 100
        assert job.state == JobState.succeeded