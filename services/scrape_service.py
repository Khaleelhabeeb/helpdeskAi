import ipaddress
import socket
from datetime import datetime
from urllib.parse import urlparse

import anyio
from bs4 import BeautifulSoup, SoupStrainer
import httpx
from fastapi import HTTPException


MAX_SCRAPE_BYTES = 2 * 1024 * 1024
SCRAPE_TIMEOUT_SECONDS = 10.0
SCRAPED_TAGS = ("title", "h1", "h2", "h3", "p", "li")


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        ip_address = ipaddress.ip_address(socket.gethostbyname(hostname))
        return not (
            ip_address.is_private
            or ip_address.is_loopback
            or ip_address.is_link_local
            or ip_address.is_multicast
        )
    except Exception:
        return False


async def _read_limited_html(url: str) -> str:
    async with httpx.AsyncClient(timeout=SCRAPE_TIMEOUT_SECONDS) as client:
        async with client.stream("GET", url, follow_redirects=True) as response:
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_SCRAPE_BYTES:
                raise ValueError("URL response is too large")

            response.raise_for_status()
            chunks: list[bytes] = []
            total_bytes = 0
            async for chunk in response.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > MAX_SCRAPE_BYTES:
                    raise ValueError("URL response is too large")
                chunks.append(chunk)

            encoding = response.encoding or "utf-8"
            return b"".join(chunks).decode(encoding, errors="replace")


def _extract_page_content(url: str, html: str) -> dict:
    soup = BeautifulSoup(
        html,
        "html.parser",
        parse_only=SoupStrainer(SCRAPED_TAGS),
    )
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    text_parts: list[str] = []
    for tag in soup.find_all(("h1", "h2", "h3", "p", "li")):
        text = tag.get_text(strip=True)
        if text:
            if tag.name in {"h1", "h2", "h3"}:
                text_parts.append(f"\n{tag.name.upper()}: {text}\n")
            else:
                text_parts.append(text)

    structured_text = "\n".join(text_parts)
    if not structured_text:
        raise ValueError("No content extracted from URL")

    return {
        "text": structured_text,
        "title": title,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def scrape_url_content(url: str) -> dict:
    if not await anyio.to_thread.run_sync(is_safe_url, url):
        raise HTTPException(status_code=400, detail="Invalid or restricted URL provided")

    try:
        html = await _read_limited_html(url)
        return _extract_page_content(url, html)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {exc}") from exc
