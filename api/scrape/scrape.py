from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pydantic import BaseModel, Field

from services.web_scraper import (
    scrape_url_content,
    scrape_url_branding,
    discover_site_links,
    crawl_site,
    scrape_multiple_urls,
)
from utils.jwt import get_current_user
from utils.rate_limit import create_limiter


router = APIRouter()
limiter = create_limiter()


class ScrapeRequest(BaseModel):
    url: str
    include_branding: bool = True


class DiscoverRequest(BaseModel):
    url: str
    limit: int = Field(default=20, ge=1, le=50)


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = Field(default=5, ge=1, le=20)


class MultiScrapeRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=10)
    concurrency: int = Field(default=3, ge=1, le=5)


async def _scrape_single_enhanced(url: str) -> dict:
    result = await scrape_url_content(url)
    return {
        "structured_text": result.get("text", ""),
        "title": result.get("title", ""),
        "final_url": result.get("final_url", url),
        "favicon_url": result.get("favicon_url"),
        "logo_url": result.get("logo_url"),
        "og_image_url": result.get("og_image_url"),
        "theme_color": result.get("theme_color"),
        "description": result.get("description"),
        "internal_links": result.get("internal_links", []),
        "timestamp": result.get("timestamp"),
    }


@router.post("")
@router.post("/")
@limiter.limit("10/minute")
async def scrape_root(request: Request, response: Response, body: ScrapeRequest, user=Depends(get_current_user)):
    return await _scrape_single_enhanced(body.url)


@router.post("/scrape")
@limiter.limit("10/minute")
async def scrape_url(request: Request, response: Response, body: ScrapeRequest, user=Depends(get_current_user)):
    return await _scrape_single_enhanced(body.url)


@router.post("/branding")
@limiter.limit("20/minute")
async def scrape_branding(request: Request, response: Response, body: ScrapeRequest, user=Depends(get_current_user)):
    result = await scrape_url_branding(body.url)
    return result


@router.post("/discover")
@limiter.limit("10/minute")
async def discover_links(request: Request, response: Response, body: DiscoverRequest, user=Depends(get_current_user)):
    result = await discover_site_links(body.url, limit=body.limit)
    return result


@router.post("/crawl")
@limiter.limit("5/minute")
async def crawl_pages(request: Request, response: Response, body: CrawlRequest, user=Depends(get_current_user)):
    result = await crawl_site(body.url, max_pages=body.max_pages)
    # Transform for frontend convenience: include structured_text alias
    pages = []
    for p in result.get("pages", []):
        if p.get("text") is not None:
            pages.append({
                "url": p.get("url"),
                "title": p.get("title"),
                "structured_text": p.get("text"),
                "description": p.get("description"),
                "success": p.get("success", True),
                "error": p.get("error"),
            })
        else:
            pages.append(p)
    return {
        "branding": result.get("branding"),
        "pages": pages,
        "discovered_links": result.get("discovered_links", []),
        "crawled_count": result.get("crawled_count", 0),
    }


@router.post("/multi")
@router.post("/batch")
@limiter.limit("10/minute")
async def multi_scrape(request: Request, response: Response, body: MultiScrapeRequest, user=Depends(get_current_user)):
    if len(body.urls) > 10:
        raise HTTPException(status_code=400, detail="Too many URLs (max 10)")
    results = await scrape_multiple_urls(body.urls, concurrency=body.concurrency)
    mapped = []
    for r in results:
        if r.get("success"):
            d = r["data"]
            mapped.append({
                "url": r["url"],
                "success": True,
                "title": d.get("title"),
                "structured_text": d.get("text"),
                "final_url": d.get("final_url", r["url"]),
                "favicon_url": d.get("favicon_url"),
                "logo_url": d.get("logo_url"),
                "og_image_url": d.get("og_image_url"),
                "theme_color": d.get("theme_color"),
                "description": d.get("description"),
                "internal_links": d.get("internal_links", []),
            })
        else:
            mapped.append({
                "url": r["url"],
                "success": False,
                "error": r.get("error"),
                "status_code": r.get("status_code"),
            })
    return {"results": mapped}
