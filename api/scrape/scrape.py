from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from services.web_scraper import scrape_url_content
from utils.jwt import get_current_user
from utils.rate_limit import create_limiter


router = APIRouter()
limiter = create_limiter()


class ScrapeRequest(BaseModel):
    url: str


@router.post("/scrape")
@limiter.limit("10/minute")
async def scrape_url(request: Request, body: ScrapeRequest, user=Depends(get_current_user)):
    result = await scrape_url_content(body.url)
    return {"structured_text": result["text"], "title": result.get("title", "")}
