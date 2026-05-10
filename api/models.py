import httpx
from fastapi import APIRouter, Depends

from utils.jwt import get_current_user
from utils.env import get_secret

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

def model_label(model: str) -> str:
    name = model.removeprefix("groq/")
    aliases = {
        "openai/gpt-oss-120b": "GPT OSS 120B",
        "openai/gpt-oss-20b": "GPT OSS 20B",
        "llama-3.3-70b-versatile": "Llama 3.3 70B Versatile",
        "llama-3.1-8b-instant": "Llama 3.1 8B Instant",
        "meta-llama/llama-4-scout-17b-16e-instruct": "Llama 4 Scout",
        "meta-llama/llama-4-maverick-17b-128e-instruct": "Llama 4 Maverick",
        "deepseek-r1-distill-llama-70b": "DeepSeek R1 Distill Llama 70B",
        "qwen/qwen3-32b": "Qwen 3 32B",
        "gemma2-9b-it": "Gemma 2 9B",
    }
    return aliases.get(name, name.replace("/", " / ").replace("-", " ").title())


def model_logo(model: str) -> str:
    name = model.removeprefix("groq/").lower()
    if "llama" in name:
        return "meta"
    if "deepseek" in name:
        return "deepseek"
    if "qwen" in name:
        return "qwen"
    if "gemma" in name:
        return "google"
    if "gpt-oss" in name:
        return "openai"
    return "groq"


@router.get("/available")
async def available_models(user=Depends(get_current_user)):
    api_key = get_secret("GROQ_API_KEY", prefixes=("gsk_",))
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

    groq_models = [
            {
                "id": model,
                "label": model_label(model),
                "provider": "groq",
                "logo": model_logo(model),
                "locked": False,
            }
            for model in sorted(set(models))
    ]

    return {"models": groq_models}
