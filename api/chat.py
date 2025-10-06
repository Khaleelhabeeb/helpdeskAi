from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.chains import LLMChain
from db import models, schemas
from api.auth import get_db
from datetime import datetime, timedelta
from typing import Optional
import uuid
import os
import time
from dotenv import load_dotenv
from services.vector_store import search, format_context

load_dotenv()

router = APIRouter()

conversation_memories = {}  

class ChatRequest(BaseModel):
    message: str
    unique_id: Optional[str] = None  

class ChatResponse(BaseModel):
    response: str
    unique_id: str  

def get_memory_key(unique_id: str, user_id: str, agent_id: str) -> str:
    """Generate a unique key for storing conversation memory."""
    return f"{unique_id}_{user_id}_{agent_id}"

def get_conversation_memory(unique_id: str, user_id: str, agent_id: str, system_prompt: str) -> LLMChain:
    """Initialize or retrieve conversation memory and LLM chain for a unique_id-user_id-agent_id triplet."""
    memory_key = get_memory_key(unique_id, user_id, agent_id)
    
    if memory_key not in conversation_memories:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

        llm = ChatGroq(
            temperature=0,
            model_name="openai/gpt-oss-20b", 
            groq_api_key=groq_api_key
        )
        
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{text}")
        ])
        
        # Create LLM chain
        conversation = LLMChain(llm=llm, prompt=prompt, memory=memory)
        conversation_memories[memory_key] = {
            "chain": conversation,
            "timestamp": time.time()  
        }
    

    conversation_memories[memory_key]["timestamp"] = time.time()
    return conversation_memories[memory_key]["chain"]

def cleanup_expired_memories():
    """Remove conversation memories older than 10 minutes."""
    expiration_time = 600
    current_time = time.time()
    keys_to_delete = [
        key for key, value in conversation_memories.items()
        if current_time - value["timestamp"] > expiration_time
    ]
    for key in keys_to_delete:
        del conversation_memories[key]
        print(f"Cleared expired memory for key: {key}")

@router.post("/{agent_id}", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: str,
    chat: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.instructions:
        raise HTTPException(status_code=400, detail="Agent has no instructions set yet")

    # Generate or use provided unique_id
    unique_id = chat.unique_id or str(uuid.uuid4())

    # Prepare system prompt (guardrails)
    system_prompt = agent.instructions or ""

    # Fetch retrieval config
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    use_retrieval = bool(cfg.retrieval_enabled) if cfg else False
    top_k = int(cfg.retrieval_top_k) if cfg else 4

    context_block = ""
    if use_retrieval:
        namespace = cfg.vector_store_namespace if cfg else None
        if namespace:
            results = search(namespace, chat.message, top_k=top_k)
            context_text = format_context(results)
            if context_text:
                system_prompt = f"{system_prompt}\n\nRelevant context (top {top_k}):\n{context_text}"

    conversation = get_conversation_memory(unique_id, "public", agent_id, system_prompt)

    conversation.memory.chat_memory.add_user_message(chat.message)

    ai_response = conversation.invoke({"text": chat.message})["text"]

    conversation.memory.chat_memory.add_ai_message(ai_response)

    background_tasks.add_task(cleanup_expired_memories)

    return ChatResponse(response=ai_response, unique_id=unique_id)