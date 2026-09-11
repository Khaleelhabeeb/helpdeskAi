import ipaddress
import os
import socket
import re
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Optional

import anyio
from bs4 import BeautifulSoup
from fastapi import HTTPException

from services.http_client import get_async_http_client


MAX_SCRAPE_BYTES = int(os.getenv("MAX_SCRAPE_BYTES", str(1024 * 1024)))
MAX_FAVICON_BYTES = int(os.getenv("MAX_FAVICON_BYTES", str(1 * 1024 * 1024)))
MAX_CRAWL_PAGES = int(os.getenv("MAX_CRAWL_PAGES", "5"))
SCRAPE_USER_AGENT = os.getenv("SCRAPE_USER_AGENT", "HelpdeskAIBot/1.0")
SCRAPE_TIMEOUT = float(os.getenv("SCRAPE_TIMEOUT_SECONDS", "10"))
CRAWL_CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "3"))


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


def _is_same_origin(url1: str, url2: str) -> bool:
    try:
        p1 = urlparse(url1)
        p2 = urlparse(url2)
        return p1.netloc.lower() == p2.netloc.lower() and p1.scheme == p2.scheme
    except Exception:
        return False


def _normalize_input_url(url: str) -> str:
    """Ensure URL has a scheme. Accepts both `example.com` and `https://example.com`."""
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if re.match(r"^[a-zA-Z][a-zA-Z\d+\-.]*://", url):
        return url
    return "https://" + url.lstrip("/")


def _resolve_url(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith("data:") or href.startswith("blob:"):
        return None
    try:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            return None
        # strip fragment, keep query
        return absolute
    except Exception:
        return None


def _extract_favicon(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    candidates: list[tuple[float, str]] = []
    for link in soup.find_all("link", href=True):
        rel_attr = link.get("rel")
        if isinstance(rel_attr, (list, tuple)):
            rel = " ".join(rel_attr).lower()
        else:
            rel = str(rel_attr or "").lower()
        href = link.get("href", "").strip()
        if not href:
            continue
        # rel can be empty; also check for icon-like href even without rel? skip for now
        if any(tok in rel for tok in ("icon", "shortcut", "apple-touch", "mask-icon", "fluid-icon")):
            resolved = _resolve_url(base_url, href)
            if not resolved:
                continue
            score = 0.0
            if "apple-touch-icon" in rel:
                score = 3.0
            elif "icon" in rel:
                sizes = link.get("sizes", "")
                # sizes may be "180x180" or "any"
                try:
                    if sizes and "x" in str(sizes):
                        # pick the biggest dimension
                        parts = re.findall(r"(\d+)x\d+", str(sizes))
                        if parts:
                            w = max(int(p) for p in parts)
                            score = 2.0 + w / 1000.0
                        else:
                            score = 2.0
                    else:
                        score = 2.0
                except Exception:
                    score = 2.0
            elif "mask-icon" in rel:
                score = 1.0
            else:
                score = 1.5
            # Prefer image types that look like icons
            type_attr = str(link.get("type", "")).lower()
            if "svg" in type_attr:
                score += 0.1
            candidates.append((score, resolved))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # fallback to /favicon.ico
    try:
        parsed = urlparse(base_url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    except Exception:
        pass
    return None


def _extract_og_image(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    for prop in ("og:image", "og:image:url", "og:image:secure_url"):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            resolved = _resolve_url(base_url, str(tag["content"]).strip())
            if resolved:
                return resolved
    for name in ("twitter:image", "twitter:image:src", "twitter:image:secure_url"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            resolved = _resolve_url(base_url, str(tag["content"]).strip())
            if resolved:
                return resolved
        tag = soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            resolved = _resolve_url(base_url, str(tag["content"]).strip())
            if resolved:
                return resolved
    # also check link rel=image_src
    tag = soup.find("link", attrs={"rel": "image_src"})
    if tag and tag.get("href"):
        resolved = _resolve_url(base_url, str(tag["href"]).strip())
        if resolved:
            return resolved
    return None


def _extract_theme_color(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": "theme-color"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    tag = soup.find("meta", attrs={"name": "msapplication-TileColor"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    # also check meta property theme-color (rare)
    tag = soup.find("meta", attrs={"property": "theme-color"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    tag = soup.find("meta", attrs={"property": "og:description"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    tag = soup.find("meta", attrs={"name": "twitter:description"})
    if tag and tag.get("content"):
        val = str(tag["content"]).strip()
        if val:
            return val
    return None


def _extract_logo_url(soup: BeautifulSoup, base_url: str, favicon_url: Optional[str], og_image_url: Optional[str]) -> Optional[str]:
    # Look for explicit logo images
    for img in soup.find_all("img", src=True):
        try:
            alt = str(img.get("alt", "")).lower()
            src = str(img.get("src", "")).lower()
            class_attr = img.get("class")
            if isinstance(class_attr, (list, tuple)):
                cls = " ".join(class_attr).lower()
            else:
                cls = str(class_attr or "").lower()
            id_attr = str(img.get("id", "")).lower()
            # Heuristic: logo-like identifiers
            if any(kw in alt for kw in ("logo", "brand")) or any(kw in src for kw in ("logo", "brand")) or any(kw in cls for kw in ("logo", "brand")) or any(kw in id_attr for kw in ("logo", "brand")):
                resolved = _resolve_url(base_url, str(img["src"]).strip())
                if resolved:
                    # filter out tiny tracking pixels?
                    width = img.get("width")
                    height = img.get("height")
                    try:
                        if width and height and int(width) < 16 and int(height) < 16:
                            continue
                    except Exception:
                        pass
                    return resolved
        except Exception:
            continue

    # Look for header logo via itemprop
    tag = soup.find(attrs={"itemprop": "logo"})
    if tag:
        src = tag.get("content") or tag.get("href") or tag.get("src")
        if src:
            resolved = _resolve_url(base_url, str(src).strip())
            if resolved:
                return resolved

    # Fallback chain: og:image -> favicon
    if og_image_url:
        return og_image_url
    return favicon_url


def _extract_internal_links(soup: BeautifulSoup, base_url: str, limit: int = 20) -> list[str]:
    parsed_base = urlparse(base_url)
    base_netloc = parsed_base.netloc.lower()
    base_scheme = parsed_base.scheme
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:") or href.startswith("data:"):
            continue
        try:
            resolved = urljoin(base_url, href)
            parsed = urlparse(resolved)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc.lower() != base_netloc:
                continue
            # Normalize - strip fragment
            clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, ""))
            # Avoid self-reference
            if clean == base_url or clean.rstrip("/") == base_url.rstrip("/"):
                continue
            # Filter common non-content URLs
            path_low = parsed.path.lower()
            # skip anchors with # already stripped, skip files that are likely not html
            if any(path_low.endswith(ext) for ext in (".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".json", ".xml", ".ico")):
                continue
            # skip query-heavy or duplicate
            if clean in seen:
                continue
            seen.add(clean)
            links.append(clean)
            if len(links) >= limit:
                break
        except Exception:
            continue
    return links


def _extract_branding(soup: BeautifulSoup, base_url: str) -> dict:
    favicon_url = _extract_favicon(soup, base_url)
    og_image_url = _extract_og_image(soup, base_url)
    theme_color = _extract_theme_color(soup)
    description = _extract_description(soup)
    logo_url = _extract_logo_url(soup, base_url, favicon_url, og_image_url)
    return {
        "favicon_url": favicon_url,
        "og_image_url": og_image_url,
        "logo_url": logo_url,
        "theme_color": theme_color,
        "description": description,
    }


def _parse_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Extract branding BEFORE decomposing? Decompose only script/style/noscript/svg, keep link/meta
    branding = _extract_branding(soup, url)
    internal_links = _extract_internal_links(soup, url, limit=25)

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # Also keep meta description as fallback title if needed
    description = branding.get("description")

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
    # If no structured text but we have description, use it
    if not structured_text:
        if description:
            structured_text = description
        else:
            # fallback to body text
            body = soup.get_text(" ", strip=True)
            if body:
                structured_text = body[:5000]
    if not structured_text:
        raise ValueError("No content extracted from URL")

    return {
        "text": structured_text,
        "title": title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "favicon_url": branding.get("favicon_url"),
        "logo_url": branding.get("logo_url"),
        "og_image_url": branding.get("og_image_url"),
        "theme_color": branding.get("theme_color"),
        "description": branding.get("description"),
        "internal_links": internal_links,
    }


async def _fetch_bytes(url: str, max_bytes: int = MAX_SCRAPE_BYTES) -> tuple[bytes, str, str]:
    """Fetch raw bytes with SSRF checks, size limiting, content-type detection.
    Returns (body_bytes, final_url, content_type)
    """
    url = _normalize_input_url(url)
    if not await is_safe_url(url):
        raise HTTPException(status_code=400, detail="Invalid or restricted URL provided")

    try:
        client = await get_async_http_client()
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": SCRAPE_USER_AGENT},
            follow_redirects=True,
            timeout=SCRAPE_TIMEOUT,
        ) as response:
            response.raise_for_status()
            final_url = str(response.url)
            if final_url != url and not await is_safe_url(final_url):
                raise HTTPException(status_code=400, detail="Invalid or restricted redirect target")

            content_type = response.headers.get("content-type", "").lower()

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Page is too large. Maximum scrape size is {max_bytes // 1024}KB.",
                    )
                chunks.append(chunk)

            body = b"".join(chunks)
            # Use response.encoding fallback
            return body, final_url, content_type
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(exc)}") from exc


async def scrape_url_content(url: str) -> dict:
    url = _normalize_input_url(url)
    body_bytes, final_url, content_type = await _fetch_bytes(url, max_bytes=MAX_SCRAPE_BYTES)

    # Validate content type
    if content_type and not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml")):
        # Allow html without content-type too
        if "text" not in content_type and "html" not in content_type:
            raise HTTPException(status_code=400, detail="URL did not return readable text or HTML")

    # Determine encoding
    # httpx stream response.encoding is not available here directly; we need to guess
    # We'll try utf-8
    try:
        body = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        body = body_bytes.decode("utf-8", errors="replace")

    # If plain text, wrap differently
    if content_type and "text/plain" in content_type and "text/html" not in content_type:
        text = body.strip()
        if not text:
            raise HTTPException(status_code=400, detail="No content extracted from URL")
        parsed = urlparse(final_url)
        title = parsed.path.split("/")[-1] or final_url
        # Still try to extract favicon via fallback
        try:
            favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        except Exception:
            favicon_url = None
        return {
            "text": text,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "favicon_url": favicon_url,
            "logo_url": favicon_url,
            "og_image_url": None,
            "theme_color": None,
            "description": text[:160] if text else None,
            "internal_links": [],
            "final_url": final_url,
        }

    result = await anyio.to_thread.run_sync(_parse_html, body, final_url)
    result["final_url"] = final_url
    return result


async def scrape_url_branding(url: str) -> dict:
    """Lightweight branding extraction without full text requirement."""
    url = _normalize_input_url(url)
    body_bytes, final_url, content_type = await _fetch_bytes(url, max_bytes=MAX_SCRAPE_BYTES)
    if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml")):
        # Fallback for non-html
        try:
            parsed = urlparse(final_url)
            favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        except Exception:
            favicon_url = None
        return {
            "final_url": final_url,
            "favicon_url": favicon_url,
            "logo_url": favicon_url,
            "og_image_url": None,
            "theme_color": None,
            "description": None,
            "title": final_url,
            "internal_links": [],
        }
    body = body_bytes.decode("utf-8", errors="replace")
    def _branding_only(html: str, base: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        branding = _extract_branding(soup, base)
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else base
        links = _extract_internal_links(soup, base, limit=25)
        branding["title"] = title
        branding["final_url"] = base
        branding["internal_links"] = links
        return branding
    return await anyio.to_thread.run_sync(_branding_only, body, final_url)


async def discover_site_links(url: str, limit: int = 20) -> dict:
    """Discover internal links and branding for a given URL."""
    url = _normalize_input_url(url)
    branding = await scrape_url_branding(url)
    # Limit links to requested amount
    links = branding.get("internal_links", [])[:limit]
    return {
        "url": branding.get("final_url", url),
        "title": branding.get("title"),
        "favicon_url": branding.get("favicon_url"),
        "logo_url": branding.get("logo_url"),
        "og_image_url": branding.get("og_image_url"),
        "theme_color": branding.get("theme_color"),
        "description": branding.get("description"),
        "internal_links": links,
    }


async def scrape_multiple_urls(urls: list[str], concurrency: int = CRAWL_CONCURRENCY) -> list[dict]:
    """Scrape multiple URLs concurrently with limit."""
    if not urls:
        return []
    # Normalize & deduplicate while preserving order
    seen = set()
    deduped: list[str] = []
    for u in urls:
        if not u:
            continue
        nu = _normalize_input_url(u.strip())
        if not nu or nu in seen:
            continue
        seen.add(nu)
        deduped.append(nu)

    semaphore = anyio.Semaphore(concurrency)

    async def _scrape_one(target_url: str) -> dict:
        async with semaphore:
            try:
                data = await scrape_url_content(target_url)
                return {"url": target_url, "success": True, "data": data}
            except HTTPException as exc:
                return {"url": target_url, "success": False, "error": exc.detail, "status_code": exc.status_code}
            except Exception as exc:
                return {"url": target_url, "success": False, "error": str(exc)}

    results: list[dict] = []

    async def _run_all():
        async with anyio.create_task_group() as tg:
            # Use list to collect results via closure
            async def _task(u: str):
                res = await _scrape_one(u)
                results.append(res)
            for u in deduped:
                tg.start_soon(_task, u)

    await _run_all()
    # Preserve original deduped order
    order = {u: i for i, u in enumerate(deduped)}
    results.sort(key=lambda x: order.get(x["url"], 0))
    return results


async def crawl_site(start_url: str, max_pages: int = 5, max_depth: int = 1, same_origin_only: bool = True) -> dict:
    """Crawl a site starting from start_url, discovering and scraping linked pages.
    max_pages includes the start_url. max_depth currently 1 (only direct children).
    """
    start_url = _normalize_input_url(start_url)
    if max_pages < 1:
        max_pages = 1
    if max_pages > 20:
        max_pages = 20

    # Step 1: scrape start URL for branding + links
    start_data = await scrape_url_content(start_url)
    branding = {
        "favicon_url": start_data.get("favicon_url"),
        "logo_url": start_data.get("logo_url"),
        "og_image_url": start_data.get("og_image_url"),
        "theme_color": start_data.get("theme_color"),
        "description": start_data.get("description"),
        "title": start_data.get("title"),
        "final_url": start_data.get("final_url", start_url),
    }
    internal_links = start_data.get("internal_links", []) or []

    # Optionally filter same_origin (already filtered in extractor, but double-check if flag)
    if same_origin_only:
        internal_links = [lnk for lnk in internal_links if _is_same_origin(start_data.get("final_url", start_url), lnk)]

    # Pick up to max_pages-1 additional pages
    to_crawl = internal_links[: max_pages - 1]

    pages: list[dict] = [
        {
            "url": start_data.get("final_url", start_url),
            "title": start_data.get("title"),
            "text": start_data.get("text"),
            "description": start_data.get("description"),
        }
    ]

    if to_crawl:
        extra_results = await scrape_multiple_urls(to_crawl, concurrency=CRAWL_CONCURRENCY)
        for item in extra_results:
            if item.get("success"):
                d = item["data"]
                pages.append({
                    "url": d.get("final_url", item["url"]),
                    "title": d.get("title"),
                    "text": d.get("text"),
                    "description": d.get("description"),
                })
            else:
                # Keep failed entries optionally
                pages.append({
                    "url": item["url"],
                    "title": None,
                    "text": None,
                    "error": item.get("error"),
                    "success": False,
                })

    return {
        "branding": branding,
        "pages": pages,
        "discovered_links": internal_links,
        "crawled_count": len(pages),
    }


async def download_image_bytes(image_url: str, max_bytes: int = MAX_FAVICON_BYTES, timeout: float = 10.0) -> tuple[bytes, str]:
    """Download image bytes with SSRF protection. Returns (bytes, content_type)."""
    image_url = _normalize_input_url(image_url)
    if not await is_safe_url(image_url):
        raise HTTPException(status_code=400, detail="Invalid or restricted image URL")
    client = await get_async_http_client()
    async with client.stream(
        "GET",
        image_url,
        headers={"User-Agent": SCRAPE_USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
        follow_redirects=True,
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        final_url = str(response.url)
        if final_url != image_url and not await is_safe_url(final_url):
            raise HTTPException(status_code=400, detail="Invalid or restricted redirect target")
        content_type = response.headers.get("content-type", "application/octet-stream").lower()
        # Allow images and ico
        if content_type and not any(kind in content_type for kind in ("image/", "application/octet-stream")) and "ico" not in content_type:
            # still allow, but not strict
            pass
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=413, detail="Image is too large")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise HTTPException(status_code=400, detail="Empty image")
        return data, content_type

