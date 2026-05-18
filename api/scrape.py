from fastapi import APIRouter
from pydantic import BaseModel

from services.scrape_service import is_safe_url, scrape_url_content


router = APIRouter()
__all__ = ["ScrapeRequest", "is_safe_url", "router", "scrape_url", "scrape_url_content"]


class ScrapeRequest(BaseModel):
    url: str


@router.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    result = await scrape_url_content(request.url)
    return {"structured_text": result["text"], "title": result.get("title", "")}
