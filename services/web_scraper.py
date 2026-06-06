import ipaddress
import os
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import anyio
from bs4 import BeautifulSoup
from fastapi import HTTPException

from services.http_client import get_async_http_client


MAX_SCRAPE_BYTES = int(os.getenv("MAX_SCRAPE_BYTES", str(1024 * 1024)))
SCRAPE_USER_AGENT = os.getenv("SCRAPE_USER_AGENT", "HelpdeskAIBot/1.0")


def _is_safe_url_sync(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        addresses = socket.getaddrinfo(hostname, None)
        for result in addresses:
            ip_obj = ipaddress.ip_address(result[4][0])
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
                return False
        return True
    except Exception:
        return False


async def is_safe_url(url: str) -> bool:
    return await anyio.to_thread.run_sync(_is_safe_url_sync, url)


def _parse_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    content: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name in ["h1", "h2", "h3"]:
            content.append(f"\n{tag.name.upper()}: {text}\n")
        else:
            content.append(text)

    structured_text = "\n".join(content).strip()
    if not structured_text:
        raise ValueError("No content extracted from URL")

    return {
        "text": structured_text,
        "title": title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def scrape_url_content(url: str) -> dict:
    if not await is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid or restricted URL provided")

    try:
        client = await get_async_http_client()
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": SCRAPE_USER_AGENT},
            follow_redirects=True,
            timeout=10.0,
        ) as response:
            response.raise_for_status()
            final_url = str(response.url)
            if final_url != url and not await is_safe_url(final_url):
                raise HTTPException(status_code=400, detail="Invalid or restricted redirect target")

            content_type = response.headers.get("content-type", "").lower()
            if content_type and not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml")):
                raise HTTPException(status_code=400, detail="URL did not return readable text or HTML")

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_SCRAPE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Page is too large. Maximum scrape size is {MAX_SCRAPE_BYTES // 1024}KB.",
                    )
                chunks.append(chunk)

        body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        return await anyio.to_thread.run_sync(_parse_html, body, url)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {str(exc)}") from exc
