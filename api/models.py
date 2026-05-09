import os

import httpx
from fastapi import APIRouter, Depends

from utils.jwt import get_current_user

router = APIRouter()

FALLBACK_GROQ_MODELS = [
    "groq/openai/gpt-oss-120b",
    "groq/openai/gpt-oss-20b",
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",
    "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/meta-llama/llama-4-maverick-17b-128e-instruct",
    "groq/deepseek-r1-distill-llama-70b",
    "groq/qwen/qwen3-32b",
    "groq/gemma2-9b-it",
]


@router.get("/available")
async def available_models(user=Depends(get_current_user)):
    api_key = (os.getenv("GROQ_API_KEY") or "").strip().strip('"')
    models = []

    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            response.raise_for_status()
            payload = response.json()
            models = [
                f"groq/{item['id']}"
                for item in payload.get("data", [])
                if item.get("id")
            ]
        except Exception as exc:
            print(f"[WARN /models/available] Failed to fetch Groq models: {exc}")

    if not models:
        models = FALLBACK_GROQ_MODELS

    return {
        "models": [
            {
                "id": model,
                "label": model.removeprefix("groq/"),
                "provider": "groq",
            }
            for model in sorted(set(models))
        ]
    }
