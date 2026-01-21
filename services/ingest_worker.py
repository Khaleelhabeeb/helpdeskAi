import os
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.database import SessionLocal
from db import models
from services.file_parser import extract_text_from_pdf_file, extract_text_from_txt_file
from langchain_text_splitters import RecursiveCharacterTextSplitter
from services.vector_store import upsert_texts
from services.s3_storage import download_text_from_s3
import httpx
import asyncio
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


def process_kb_ingest_job(job_id: str, transient_text: Optional[str] = None) -> None:
    """
    Background task to process a KB ingest job.
    - Looks up the job and KB
    - Marks job running, then succeeded/failed
    - Sets KB status accordingly
    - Does NOT store chunks or embeddings in Postgres
    - Does NOT perform retrieval; this is a scaffold

    transient_text: when source_type == text, use this inline payload for processing;
                    do not persist to DB.
    """
    db: Session = SessionLocal()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if not job:
            return
        kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
        if not kb:
            job.state = models.JobState.failed
            job.error = "KB not found"
            db.commit()
            return

        # Mark running
        job.state = models.JobState.running
        db.commit()

        # Read minimal info for vector upsert
        agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id).first()
        config = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == kb.agent_id).first()
        namespace = config.vector_store_namespace if config else None

        # Download extracted text from S3 (all types store extracted text there)
        text_content: Optional[str] = None
        
        if kb.s3_extracted_key:
            # Use cached extracted text from S3
            text_content = download_text_from_s3(kb.s3_extracted_key)
            if not text_content:
                raise ValueError("Failed to download extracted text from S3")
        else:
            # Fallback: shouldn't happen with new uploads, but handle legacy
            if kb.source_type in (models.KBSourceType.upload_pdf, models.KBSourceType.upload_txt, models.KBSourceType.other):
                if not kb.source_uri or not os.path.exists(kb.source_uri):
                    raise FileNotFoundError("KB source file not found and no S3 backup")
                lower = kb.source_uri.lower()
                if lower.endswith(".pdf"):
                    with open(kb.source_uri, "rb") as rf:
                        text_content = extract_text_from_pdf_file(rf)
                elif lower.endswith(".txt"):
                    with open(kb.source_uri, "rb") as rf:
                        text_content = extract_text_from_txt_file(rf)
                else:
                    with open(kb.source_uri, "rb") as rf:
                        text_content = rf.read().decode("utf-8", errors="ignore")
            elif kb.source_type == models.KBSourceType.text:
                if transient_text is None or len(transient_text.strip()) == 0:
                    raise ValueError("No transient text provided for text KB")
                text_content = transient_text

        if not text_content or len(text_content.strip()) == 0:
            raise ValueError("No text content extracted for KB")

        # Chunking
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = [c for c in splitter.split_text(text_content) if c.strip()]
        if not chunks:
            raise ValueError("No chunks generated from content")

        if not namespace:
            raise ValueError("Missing vector store namespace")
        upsert_texts(namespace=namespace, kb_id=str(kb.id), agent_id=str(agent.id), texts=chunks, metadatas=None)

        # Update KB with chunk count
        kb.chunk_count = len(chunks)
        kb.status = models.KBStatus.ready
        
        # Mark job success
        job.state = models.JobState.succeeded
        job.error = None
        db.commit()
    except Exception as e:
        try:
            job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
            if job:
                job.state = models.JobState.failed
                job.error = str(e)
                kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
                if kb:
                    kb.status = models.KBStatus.failed
            db.commit()
        except SQLAlchemyError:
            db.rollback()
    finally:
        db.close()
