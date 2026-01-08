from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from typing import Optional
from sqlalchemy.orm import Session
from db import schemas, models, database
from utils.jwt import get_current_user
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str


async def scrape_url_content(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = tag.get_text(strip=True)
            if text:
                if tag.name in ['h1', 'h2', 'h3']:
                    content.append(f"\n{tag.name.upper()}: {text}\n")
                else:
                    content.append(text)
        structured_text = '\n'.join(content)
        if not structured_text:
            raise ValueError("No content extracted from URL")
        return structured_text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {str(e)}")

@router.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    # logger.debug(f"Received scrape request for URL: {request.url}")
    structured_text = await scrape_url_content(request.url)
    return {"structured_text": structured_text}

