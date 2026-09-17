from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db import schemas
from api.auth.auth import get_db
from db import models
from utils.jwt import get_current_user
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from models.widget_deployment import new_deployment_id
from services.chat_runtime import invalidate_agent_runtime
from services.redis_client import cache_key, redis_delete

router = APIRouter()


def _get_or_create_widget_deployment(db: Session, agent: models.Agent) -> models.WidgetDeployment:
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
    if deployment:
        return deployment
    deployment = models.WidgetDeployment(
        agent_id=agent.id,
        deployment_id=new_deployment_id(),
        display_name=agent.name,
        logo_url=agent.avatar_url,
        initial_messages=[f"Hi! How can {agent.name} help you today?"],
        theme="dark",
        primary_color="#ffffff",
        allowed_domains=["localhost", "127.0.0.1"],
        is_enabled=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


@router.get("/{agent_id}/settings", response_model=schemas.AgentSettingsOut)
def get_agent_settings(
    agent_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        config = db.query(models.AgentConfig).filter(
            models.AgentConfig.agent_id == agent_id
        ).first()
    except Exception:
        # Column human_handoff_enabled may not exist yet (pre-migration) — feature defaults OFF
        db.rollback()
        config = None
    
    kb_count = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.agent_id == agent_id
    ).count()
    
    total_conversations = db.query(models.UsageLog).filter(
        models.UsageLog.agent_id == agent_id
    ).count()
    
    widget_config = {
        "theme": (getattr(config, 'widget_theme', None) if config else None) or 'light',
        "color": (getattr(config, 'widget_color', None) if config else None) or '#4a6cf7',
        "position": (getattr(config, 'widget_position', None) if config else None) or 'bottom-right',
        "greeting": (getattr(config, 'widget_greeting', None) if config else None) or f'Hi! How can {agent.name} help you today?',
        "use_color_header": bool(getattr(config, 'widget_use_color_header', False)) if config else False,
    }
    # Human handoff toggle + difficulty — effective only if team exists
    has_team = False
    active_human_count = 0
    if agent:
        active_human_count = db.query(models.HumanAgent).join(
            models.AgentAssignment, models.HumanAgent.id == models.AgentAssignment.human_agent_id
        ).filter(
            models.AgentAssignment.agent_id == agent_id,
            models.HumanAgent.status == 'active'
        ).count()
        has_team = active_human_count > 0
    handoff_enabled_cfg = bool(getattr(config, 'human_handoff_enabled', False)) if config else False
    raw_diff = (getattr(config, 'human_handoff_difficulty', 'balanced') or 'balanced') if config else 'balanced'
    handoff_difficulty = raw_diff if raw_diff in ('easy','balanced','hard') else 'balanced'
    handoff_effective = handoff_enabled_cfg and has_team
    
    base_url = str(request.base_url).rstrip('/')
    deployment = _get_or_create_widget_deployment(db, agent)
    embed_script = f'''<!-- {agent.name} Chat Widget -->
<script
    src="{base_url}/static/widget.js?v=2.1.2"
    data-deployment-id="{deployment.deployment_id}"
    defer
></script>'''
    
    npm_install = f"# Coming soon: npm install @helpdeskAi/widget"
    
    return {
        "agent_id": str(agent_id),
        "name": agent.name,
        "instructions": agent.instructions or "",
        "model": agent.model,
        "widget": widget_config,
        "embed": {
            "script": embed_script,
            "preview_url": f"{base_url}/preview/{agent_id}",
            "test_url": f"{base_url}/test-widget?agent={agent_id}",
            "npm_install": npm_install
        },
        "statistics": {
            "knowledge_bases": kb_count,
            "total_conversations": total_conversations,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": config.updated_at.isoformat() if config and config.updated_at else None
        },
        "human_handoff": {
            "enabled": handoff_enabled_cfg,
            "difficulty": handoff_difficulty,
            "effective": handoff_effective,
            "has_team": has_team,
            "active_human_count": active_human_count,
            "options": {
                "easy": {"label": "Easy — offers human quickly after one try", "short": "Quick handoff"},
                "balanced": {"label": "Balanced — tries 1–2 steps then offers", "short": "Thoughtful"},
                "hard": {"label": "Hard — persists, needs insistence twice", "short": "Persistent"},
            },
        }
    }


@router.patch("/{agent_id}/settings")
def update_agent_settings(
    agent_id: UUID,
    settings: schemas.AgentSettingsUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    try:
        config = db.query(models.AgentConfig).filter(
            models.AgentConfig.agent_id == agent_id
        ).first()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="Human handoff toggle requires DB migration. Run `alembic upgrade head`.")

    if not config:
        config = models.AgentConfig(agent_id=agent_id)
        db.add(config)
    
    updates = []
    
    if settings.name is not None:
        agent.name = settings.name
        updates.append("name")
    
    if settings.instructions is not None:
        agent.instructions = settings.instructions
        updates.append("instructions")

    if settings.model is not None:
        agent.model = settings.model
        updates.append("model")
    
    if settings.widget_theme is not None:
        config.widget_theme = settings.widget_theme
        updates.append("widget_theme")
    
    if settings.widget_color is not None:
        config.widget_color = settings.widget_color
        updates.append("widget_color")
    
    if settings.widget_position is not None:
        config.widget_position = settings.widget_position
        updates.append("widget_position")
    
    if settings.widget_greeting is not None:
        config.widget_greeting = settings.widget_greeting
        updates.append("widget_greeting")

    if settings.widget_use_color_header is not None:
        config.widget_use_color_header = settings.widget_use_color_header
        updates.append("widget_use_color_header")

    if settings.human_handoff_enabled is not None:
        # Allow toggling even without team — effective will remain false until a human is assigned & active.
        # Previously we blocked here with 400 and the UI looked like it "snapped back" off.
        config.human_handoff_enabled = bool(settings.human_handoff_enabled)
        updates.append("human_handoff_enabled")

    if settings.human_handoff_difficulty is not None:
        if settings.human_handoff_difficulty not in ('easy','balanced','hard'):
            raise HTTPException(status_code=422, detail="Difficulty must be one of: easy, balanced, hard")
        # Only allow setting difficulty if handoff is enabled or being enabled in same patch
        cfg_enabled = bool(getattr(config, 'human_handoff_enabled', False))
        will_be_enabled = settings.human_handoff_enabled if settings.human_handoff_enabled is not None else cfg_enabled
        if not will_be_enabled and settings.human_handoff_difficulty != 'balanced':
            # Still allow but warn — difficulty is stored but not effective until enabled
            pass
        config.human_handoff_difficulty = settings.human_handoff_difficulty
        updates.append("human_handoff_difficulty")
    
    config.updated_at = datetime.now(timezone.utc)
    
    try:
        db.commit()
        db.refresh(agent)
        db.refresh(config)
        invalidate_agent_runtime(str(agent.id), agent.user_id)
        deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
        if deployment:
            redis_delete(cache_key("widget", "config", deployment.deployment_id))
        
        return {
            "success": True,
            "message": f"Agent settings updated successfully",
            "updated_fields": updates,
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "instructions": agent.instructions,
                "model": agent.model,
                "updated_at": config.updated_at.isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/{agent_id}/settings/reset-widget")
def reset_widget_settings(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    if not config:
        config = models.AgentConfig(agent_id=agent_id)
        db.add(config)
    
    config.widget_theme = 'light'
    config.widget_color = '#4a6cf7'
    config.widget_position = 'bottom-right'
    config.widget_greeting = f'Hi! How can {agent.name} help you today?'
    config.widget_use_color_header = False
    config.updated_at = datetime.now(timezone.utc)
    
    try:
        db.commit()
        db.refresh(config)
        invalidate_agent_runtime(str(agent.id), agent.user_id)
        deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
        if deployment:
            redis_delete(cache_key("widget", "config", deployment.deployment_id))
        
        return {
            "success": True,
            "message": "Widget settings reset to defaults",
            "defaults": {
                "theme": config.widget_theme,
                "color": config.widget_color,
                "position": config.widget_position,
                "greeting": config.widget_greeting,
                "use_color_header": config.widget_use_color_header
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset widget settings: {str(e)}")


@router.get("/{agent_id}/handoff")
def get_handoff_settings(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        config = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent_id).first()
        enabled_cfg = bool(getattr(config, 'human_handoff_enabled', False)) if config else False
        raw_diff = (getattr(config, 'human_handoff_difficulty', 'balanced') or 'balanced') if config else 'balanced'
        difficulty = raw_diff if raw_diff in ('easy','balanced','hard') else 'balanced'
    except Exception:
        db.rollback()
        enabled_cfg = False
        difficulty = 'balanced'
    active_count = db.query(models.HumanAgent).join(models.AgentAssignment, models.HumanAgent.id == models.AgentAssignment.human_agent_id).filter(models.AgentAssignment.agent_id == agent_id, models.HumanAgent.status=='active').count()
    has_team = active_count > 0
    return {"agent_id": str(agent_id), "enabled": enabled_cfg, "difficulty": difficulty, "effective": enabled_cfg and has_team, "has_team": has_team, "active_human_count": active_count}


@router.patch("/{agent_id}/handoff")
def patch_handoff_settings(
    agent_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if "enabled" not in payload and "difficulty" not in payload:
        raise HTTPException(status_code=422, detail="Provide 'enabled' boolean and/or 'difficulty' (easy|balanced|hard)")
    try:
        config = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent_id).first()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="Handoff feature requires DB migration. Run `alembic upgrade head`.")
    if not config:
        config = models.AgentConfig(agent_id=agent_id)
        db.add(config)
        db.flush()
    if "enabled" in payload:
        enabled = bool(payload["enabled"])
        # Allow enabling even without assigned humans — effective stays false until assignment happens
        config.human_handoff_enabled = enabled
    if "difficulty" in payload:
        diff = str(payload["difficulty"]).strip().lower()
        if diff not in ('easy','balanced','hard'):
            raise HTTPException(status_code=422, detail="Difficulty must be one of: easy, balanced, hard")
        config.human_handoff_difficulty = diff
    config.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)
    invalidate_agent_runtime(str(agent.id), agent.user_id)
    active_count2 = db.query(models.HumanAgent).join(models.AgentAssignment, models.HumanAgent.id == models.AgentAssignment.human_agent_id).filter(models.AgentAssignment.agent_id == agent_id, models.HumanAgent.status=='active').count()
    enabled2 = bool(getattr(config, 'human_handoff_enabled', False))
    diff2 = getattr(config, 'human_handoff_difficulty', 'balanced') or 'balanced'
    return {"agent_id": str(agent_id), "enabled": enabled2, "difficulty": diff2, "effective": enabled2 and active_count2>0, "has_team": active_count2>0, "active_human_count": active_count2}


@router.get("/{agent_id}/embed-code")
def get_embed_code(
    agent_id: UUID,
    request: Request,
    theme: Optional[str] = None,
    color: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    widget_color = color or (getattr(config, 'widget_color', '#4a6cf7') if config else '#4a6cf7')
    widget_theme = theme or (getattr(config, 'widget_theme', 'light') if config else 'light')
    
    if color and not color.startswith('#'):
        raise HTTPException(status_code=400, detail="Color must be in hex format (e.g., #4a6cf7)")
    
    base_url = str(request.base_url).rstrip('/')
    deployment = _get_or_create_widget_deployment(db, agent)
    embed_script = f'''<!-- {agent.name} Chat Widget -->
<script
    src="{base_url}/static/widget.js?v=2.1.2"
    data-deployment-id="{deployment.deployment_id}"
    defer
></script>'''
    
    return {
        "agent_name": agent.name,
        "embed_script": embed_script,
        "configuration": {
            "theme": widget_theme,
            "color": widget_color,
            "agent_id": str(agent_id)
        },
        "preview_url": f"{base_url}/preview/{agent_id}?color={widget_color.replace('#', '')}"
    }
