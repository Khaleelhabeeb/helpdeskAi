import pytest
from sqlalchemy import select
from sqlalchemy.exc import DataError

from models import KnowledgeBase, KBIngestJob
from models.enums import KBSourceType, KBStatus, JobState


class TestKBSourceTypeEnum:
    def test_all_values(self):
        assert KBSourceType.upload_pdf.value == "upload_pdf"
        assert KBSourceType.upload_txt.value == "upload_txt"
        assert KBSourceType.url.value == "url"
        assert KBSourceType.text.value == "text"
        assert KBSourceType.other.value == "other"

    def test_enum_in_model(self, db_session, agent):
        for source_type in KBSourceType:
            kb = KnowledgeBase(agent_id=agent.id, source_type=source_type)
            db_session.add(kb)
        db_session.commit()

        kbs = db_session.execute(select(KnowledgeBase)).scalars().all()
        assert len(kbs) == 5
        stored = {kb.source_type for kb in kbs}
        assert stored == set(KBSourceType)


class TestKBStatusEnum:
    def test_all_values(self):
        assert KBStatus.pending.value == "pending"
        assert KBStatus.ready.value == "ready"
        assert KBStatus.failed.value == "failed"

    def test_enum_in_model(self, db_session, agent):
        for status in KBStatus:
            kb = KnowledgeBase(agent_id=agent.id, source_type=KBSourceType.text, status=status)
            db_session.add(kb)
        db_session.commit()

        kbs = db_session.execute(select(KnowledgeBase)).scalars().all()
        assert len(kbs) == 3
        stored = {kb.status for kb in kbs}
        assert stored == set(KBStatus)

    def test_default_status(self, db_session, agent):
        kb = KnowledgeBase(agent_id=agent.id, source_type=KBSourceType.text)
        db_session.add(kb)
        db_session.commit()
        db_session.refresh(kb)

        assert kb.status == KBStatus.pending


class TestJobStateEnum:
    def test_all_values(self):
        assert JobState.queued.value == "queued"
        assert JobState.running.value == "running"
        assert JobState.succeeded.value == "succeeded"
        assert JobState.failed.value == "failed"

    def test_enum_in_model(self, db_session, knowledge_base):
        for state in JobState:
            job = KBIngestJob(kb_id=knowledge_base.id, state=state)
            db_session.add(job)
        db_session.commit()

        jobs = db_session.execute(select(KBIngestJob)).scalars().all()
        assert len(jobs) == 4
        stored = {job.state for job in jobs}
        assert stored == set(JobState)

    def test_default_state(self, db_session, knowledge_base):
        job = KBIngestJob(kb_id=knowledge_base.id)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.state == JobState.queued


class TestEnumStorage:
    def test_enums_stored_as_strings_in_db(self, db_session, agent, knowledge_base):
        kb = KnowledgeBase(
            agent_id=agent.id,
            source_type=KBSourceType.upload_pdf,
            status=KBStatus.ready,
        )
        db_session.add(kb)
        db_session.commit()

        result = db_session.execute(
            select(KnowledgeBase.source_type, KnowledgeBase.status)
            .where(KnowledgeBase.id == kb.id)
        ).one()

        assert result.source_type == "upload_pdf"
        assert result.status == "ready"

    def test_invalid_enum_raises_error(self, db_session, agent):
        kb = KnowledgeBase(agent_id=agent.id, source_type="invalid_type")
        db_session.add(kb)
        with pytest.raises(DataError):
            db_session.commit()