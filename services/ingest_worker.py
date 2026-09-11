import logging
import mimetypes
import os
import anyio
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.database import BackgroundSession
from db import models
from services.rag_service import aindex_kb_text
from services.kb_limits import enforce_text_limit
from services.web_scraper import scrape_url_content
from services.file_parser import extract_text_from_file
from services.kb_source_storage import download_kb_source
from services.vector_store import delete_for_kb
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


async def _try_assign_branding_to_agent(db: Session, agent: models.Agent, favicon_url: Optional[str], theme_color: Optional[str]) -> None:
    """Assign favicon/logo and theme color to agent/widget if not already set."""
    # Assign avatar/logo if missing
    if favicon_url and not agent.avatar_url:
        try:
            from services.web_scraper import download_image_bytes, is_safe_url
            from services.image_upload import upload_avatar_image, ImageUploadError
            from services.redis_client import cache_key, redis_delete
            if await is_safe_url(favicon_url):
                try:
                    img_bytes, content_type = await download_image_bytes(favicon_url)
                    parsed = favicon_url.split("?")[0].split("/")[-1] or "favicon"
                    ext = mimetypes.guess_extension(content_type or "") or ".png"
                    if "." not in parsed:
                        parsed = f"favicon{ext}"
                    worker_configured = bool(os.getenv("IMAGE_WORKER_URL") and os.getenv("IMAGE_WORKER_API_KEY"))
                    if worker_configured:
                        try:
                            result = await upload_avatar_image(img_bytes, parsed, content_type or "image/png")
                            final_url = result.url
                        except ImageUploadError:
                            final_url = favicon_url
                    else:
                        final_url = favicon_url
                    agent.avatar_url = final_url
                    db.commit()
                    db.refresh(agent)
                    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
                    if deployment:
                        if not deployment.logo_url:
                            deployment.logo_url = final_url
                            redis_delete(cache_key("widget", "config", deployment.deployment_id))
                            db.commit()
                    else:
                        from models.widget_deployment import new_deployment_id
                        from datetime import datetime, timezone
                        deployment = models.WidgetDeployment(
                            agent_id=agent.id,
                            deployment_id=new_deployment_id(),
                            display_name=agent.name,
                            logo_url=final_url,
                            initial_messages=["Hi! What can I help you with?"],
                            theme="dark",
                            primary_color="#ffffff",
                            allowed_domains=["localhost", "127.0.0.1"],
                            is_enabled=True,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                        db.add(deployment)
                        db.commit()
                except Exception as dl_exc:
                    logger.info("ingest_favicon_download_failed agent_id=%s err=%s", agent.id, dl_exc)
                    # fallback direct URL
                    agent.avatar_url = favicon_url
                    db.commit()
                    db.refresh(agent)
                    from services.redis_client import cache_key, redis_delete
                    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
                    if deployment and not deployment.logo_url:
                        deployment.logo_url = favicon_url
                        redis_delete(cache_key("widget", "config", deployment.deployment_id))
                        db.commit()
        except Exception as exc:
            logger.info("ingest_favicon_assign_failed agent_id=%s err=%s", agent.id, exc)

    # Assign theme color to config/deployment if valid and not already customized
    if theme_color and isinstance(theme_color, str) and theme_color.startswith("#") and len(theme_color) == 7:
        try:
            int(theme_color[1:], 16)
            cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
            if cfg and cfg.widget_color in (None, "#4a6cf7", "#ffffff"):
                cfg.widget_color = theme_color
                cfg.widget_use_color_header = True
                db.commit()
            deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
            if deployment and deployment.primary_color in ("#ffffff", "#4a6cf7"):
                from services.redis_client import cache_key, redis_delete
                deployment.primary_color = theme_color
                from datetime import datetime, timezone
                deployment.updated_at = datetime.now(timezone.utc)
                redis_delete(cache_key("widget", "config", deployment.deployment_id))
                db.commit()
        except Exception:
            pass


async def process_kb_ingest_job(
    job_id: str,
    transient_text: Optional[str] = None,
    transient_text_path: Optional[str] = None,
) -> None:
    """
    Worker function to process a KB ingest job.
    - Looks up the job and KB
    - Marks job running, then succeeded/failed
    - Sets KB status accordingly
    - Does NOT store chunks or embeddings in Postgres
    - Writes embeddings to the configured vector store

    transient_text_path: temporary spool file supplied by the ingest queue.
    """
    db: Session = BackgroundSession()
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
        job.processed_chunks = 0
        job.total_chunks = None
        db.commit()

        # Read minimal info for vector upsert
        agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id).first()
        config = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == kb.agent_id).first()
        namespace = config.vector_store_namespace if config else None

        text_content: Optional[str] = None
        
        if transient_text_path:
            text_content = Path(transient_text_path).read_text(encoding="utf-8")
        elif transient_text is not None and len(transient_text.strip()) > 0:
            text_content = transient_text
        elif kb.source_type == models.KBSourceType.url and kb.source_uri:
            scraped_data = await scrape_url_content(kb.source_uri)
            text_content = scraped_data.get("text", "")
            kb.title = kb.title or scraped_data.get("title")
            kb.extracted_size_bytes = enforce_text_limit(text_content)
            db.commit()
            # Try to assign favicon/logo to agent if not already set (branding propagation)
            try:
                if agent and not agent.avatar_url:
                    favicon_candidate = scraped_data.get("logo_url") or scraped_data.get("favicon_url") or scraped_data.get("og_image_url")
                    theme_color = scraped_data.get("theme_color")
                    if favicon_candidate or theme_color:
                        await _try_assign_branding_to_agent(db, agent, favicon_candidate, theme_color)
            except Exception as br_exc:
                logger.info("ingest_branding_assign_failed kb_id=%s err=%s", kb.id, br_exc)
        elif kb.source_storage_url:
            source_bytes = await download_kb_source(kb.source_storage_url)
            filename = kb.original_filename or kb.title or f"{kb.id}.txt"
            text_content = await anyio.to_thread.run_sync(extract_text_from_file, source_bytes, filename)
            kb.extracted_size_bytes = enforce_text_limit(text_content)
            db.commit()

        if not text_content or len(text_content.strip()) == 0:
            raise ValueError("No text content extracted for KB")

        if not agent:
            raise ValueError("Agent not found for KB")
        if not namespace:
            raise ValueError("Missing vector store namespace")

        await anyio.to_thread.run_sync(lambda: delete_for_kb(namespace, str(kb.id)))

        def update_progress(done_chunks: int, total_chunks: int) -> None:
            job.total_chunks = total_chunks
            job.processed_chunks = done_chunks
            kb.chunk_count = done_chunks
            db.commit()

        chunk_count = await aindex_kb_text(
            db=db,
            user_id=agent.user_id,
            agent_id=str(agent.id),
            kb_id=str(kb.id),
            namespace=namespace,
            text_value=text_content,
            on_batch=update_progress,
        )

        # Update KB with chunk count
        kb.chunk_count = chunk_count
        kb.status = models.KBStatus.ready
        
        # Mark job success
        job.state = models.JobState.succeeded
        job.error = None
        db.commit()
    except Exception as e:
        logger.exception("kb_ingest_job_failed job_id=%s", job_id)
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
        if transient_text_path:
            try:
                Path(transient_text_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", transient_text_path)
        db.close()
