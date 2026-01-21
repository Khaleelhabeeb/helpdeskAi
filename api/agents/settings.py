from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db import schemas
from api.auth.auth import get_db
from db import models
from utils.jwt import get_current_user
from typing import Optional
from uuid import UUID
from datetime import datetime

router = APIRouter()


@router.get("/{agent_id}/settings", response_model=schemas.AgentSettingsOut)
def get_agent_settings(
    agent_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get complete settings: basic info, widget config, embed script, and statistics
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get agent config
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    # Get knowledge base count
    kb_count = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.agent_id == agent_id
    ).count()
    
    # Get total conversations
    total_conversations = db.query(models.UsageLog).filter(
        models.UsageLog.agent_id == agent_id
    ).count()
    
    # Get widget configuration (from AgentConfig or use defaults)
    widget_config = {
        "theme": getattr(config, 'widget_theme', 'light') if config else 'light',
        "color": getattr(config, 'widget_color', '#4a6cf7') if config else '#4a6cf7',
        "position": getattr(config, 'widget_position', 'bottom-right') if config else 'bottom-right',
        "greeting": getattr(config, 'widget_greeting', f'Hi! How can {agent.name} help you today?') if config else f'Hi! How can {agent.name} help you today?'
    }
    
    # Generate embed script
    base_url = str(request.base_url).rstrip('/')
    embed_script = f'''<!-- {agent.name} Chat Widget -->
<script
    src="{base_url}/static/widget.js"
    data-agent-id="{agent_id}"
    display-name="{agent.name}"
    main-color="{widget_config['color']}"
    defer
></script>'''
    
    # Alternative: npm/yarn package instructions
    npm_install = f"# Coming soon: npm install @helpdeskAi/widget"
    
    return {
        "agent_id": str(agent_id),
        "name": agent.name,
        "instructions": agent.instructions or "",
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
        }
    }


@router.patch("/{agent_id}/settings")
def update_agent_settings(
    agent_id: UUID,
    settings: schemas.AgentSettingsUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Update agent settings: name, instructions, widget theme/color/position/greeting (partial updates supported)
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get or create agent config
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    if not config:
        config = models.AgentConfig(agent_id=agent_id)
        db.add(config)
    
    # Track what was updated
    updates = []
    
    # Update agent basic info
    if settings.name is not None:
        agent.name = settings.name
        updates.append("name")
    
    if settings.instructions is not None:
        agent.instructions = settings.instructions
        updates.append("instructions")
    
    # Update widget configuration in AgentConfig
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
    
    # Update timestamp
    config.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(agent)
        db.refresh(config)
        
        return {
            "success": True,
            "message": f"Agent settings updated successfully",
            "updated_fields": updates,
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "instructions": agent.instructions,
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
    # Reset widget to defaults: light theme, #4a6cf7 color, bottom-right position, auto-generated greeting
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get or create agent config
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    if not config:
        config = models.AgentConfig(agent_id=agent_id)
        db.add(config)
    
    # Reset to defaults
    config.widget_theme = 'light'
    config.widget_color = '#4a6cf7'
    config.widget_position = 'bottom-right'
    config.widget_greeting = f'Hi! How can {agent.name} help you today?'
    config.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(config)
        
        return {
            "success": True,
            "message": "Widget settings reset to defaults",
            "defaults": {
                "theme": config.widget_theme,
                "color": config.widget_color,
                "position": config.widget_position,
                "greeting": config.widget_greeting
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset widget settings: {str(e)}")


@router.get("/{agent_id}/embed-code")
def get_embed_code(
    agent_id: UUID,
    request: Request,
    theme: Optional[str] = None,
    color: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Generate embed code with optional theme/color overrides for testing before saving
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get saved config
    config = db.query(models.AgentConfig).filter(
        models.AgentConfig.agent_id == agent_id
    ).first()
    
    # Use overrides or fall back to saved config or defaults
    widget_color = color or (getattr(config, 'widget_color', '#4a6cf7') if config else '#4a6cf7')
    widget_theme = theme or (getattr(config, 'widget_theme', 'light') if config else 'light')
    
    # Validate color format if provided
    if color and not color.startswith('#'):
        raise HTTPException(status_code=400, detail="Color must be in hex format (e.g., #4a6cf7)")
    
    # Generate embed script
    base_url = str(request.base_url).rstrip('/')
    embed_script = f'''<!-- {agent.name} Chat Widget -->
<script
    src="{base_url}/static/widget.js"
    data-agent-id="{agent_id}"
    display-name="{agent.name}"
    main-color="{widget_color}"
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
