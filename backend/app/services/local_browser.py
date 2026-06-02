"""Local, no-paid-API web search + page scraping for the web agent.

Drives a headless Chromium (Playwright) on this machine to search DuckDuckGo's
HTML endpoint and to scrape arbitrary pages, then cleans the HTML with
BeautifulSoup into agent-ready markdown/text. No Google/Tavily/SerpAPI keys.

Resilience by design — every layer degrades gracefully so the app never breaks:
  1. Playwright (headless Chromium) — the primary path.
  2. httpx + BeautifulSoup — used when Playwright/Chromium isn't installed, or a
     navigation fails. DuckDuckGo's /html/ endpoint is static, so this works.
  3. Deterministic stubs — under USE_STUBS (dev/tests), so nothing hits the
     network and the suite stays hermetic.

Bot-bypass basics for a home connection: a realistic desktop User-Agent, an
Accept-Language header, a normal viewport, sane timeouts, and a block-page
detector that triggers the next fallback instead of returning a captcha page.

All Playwright/BeautifulSoup imports are lazy so the backend imports cleanly
even when the optional deps aren't installed.
"""
from __future__ import annotations

import re
import threading
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from app.core.config import settings
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.local_browser")

DDG_HTML = "https://html.duckduckgo.com/html/"
DDG_LITE = "https://lite.duckduckgo.com/lite/"
_BLOCK_MARKERS = ("unusual traffic", "captcha", "are you a robot", "verify you are human")


# ── Threading guard ──────────────────────────────────────────────────────────
def _run_blocking(fn):
    """Run a blocking (sync Playwright) callable safely even if an asyncio loop
    is running in the current thread — Playwright's sync API refuses to run
    inside a live event loop, so we hop to a worker thread when one exists.
    Our actual call sites (sync endpoints / scheduler) have no loop, so this is
    usually a direct call."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn()  # no loop — safe to run inline

    result: dict = {}

    def _worker():
        try:
            result["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


# ── DuckDuckGo result-link decoding ──────────────────────────────────────────
def _decode_ddg_href(href: str) -> str:
    """DuckDuckGo wraps result links as //duckduckgo.com/l/?uddg=<encoded>."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
    except Exception:  # noqa: BLE001
        pass
    return href


def _looks_blocked(text: str) -> bool:
    low = (text or "").lower()
    return len(low) < 200 and any(m in low for m in _BLOCK_MARKERS)


# ── HTML cleaning (BeautifulSoup) ────────────────────────────────────────────
_STRIP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside",
               "form", "svg", "iframe", "button", "input")


def clean_html(html: str, url: str = "") -> dict:
    """Strip scripts/CSS/nav/chrome and return {title, text, markdown}. Uses
    BeautifulSoup; markdownify if available, else a plain-text extraction."""
    try:
        from bs4 import BeautifulSoup  # lazy
    except ImportError:
        # No BS4 — last resort: crude tag strip so callers still get text.
        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", text).strip()
        return {"title": "", "text": text[: settings.WEB_SCRAPE_MAX_CHARS], "markdown": text[: settings.WEB_SCRAPE_MAX_CHARS]}

    soup = BeautifulSoup(html or "", "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()
    # Prefer the main content region when the page marks one.
    main = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup

    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    text = re.sub(r"[ \t]{2,}", " ", text)[: settings.WEB_SCRAPE_MAX_CHARS]

    markdown = text
    try:
        from markdownify import markdownify as _md  # lazy, optional

        markdown = _md(str(main), heading_style="ATX", strip=["a"]).strip()
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)[: settings.WEB_SCRAPE_MAX_CHARS]
    except Exception:  # noqa: BLE001
        pass

    return {"title": title, "text": text, "markdown": markdown}


# ── Search: httpx fallback ───────────────────────────────────────────────────
def _headers() -> dict:
    return {
        "User-Agent": settings.WEB_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _search_httpx(query: str, max_results: int) -> list[dict]:
    import httpx
    from bs4 import BeautifulSoup

    timeout = settings.WEB_FETCH_TIMEOUT_SECONDS
    resp = httpx.post(
        DDG_HTML, data={"q": query}, headers=_headers(), timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    if _looks_blocked(resp.text):
        raise RuntimeError("ddg_blocked")
    soup = BeautifulSoup(resp.text, "html.parser")
    out: list[dict] = []
    for res in soup.select("div.result, div.web-result")[: max_results * 2]:
        a = res.select_one("a.result__a")
        if not a:
            continue
        url = _decode_ddg_href(a.get("href", ""))
        if not url.startswith("http"):
            continue
        snippet_el = res.select_one(".result__snippet")
        out.append({
            "title": a.get_text(strip=True),
            "url": url,
            "snippet": (snippet_el.get_text(strip=True) if snippet_el else "")[:300],
        })
        if len(out) >= max_results:
            break
    return out


# ── Search: Playwright ───────────────────────────────────────────────────────
def _search_playwright(query: str, max_results: int) -> list[dict]:
    from playwright.sync_api import sync_playwright  # lazy
    from bs4 import BeautifulSoup

    def _do() -> list[dict]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.BROWSER_HEADLESS)
            try:
                ctx = browser.new_context(
                    user_agent=settings.WEB_USER_AGENT,
                    locale="en-US",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                page = ctx.new_page()
                page.goto(f"{DDG_HTML}?q={quote_plus(query)}",
                          wait_until="domcontentloaded",
                          timeout=settings.BROWSER_NAV_TIMEOUT_MS)
                html = page.content()
            finally:
                browser.close()
        if _looks_blocked(html):
            raise RuntimeError("ddg_blocked")
        soup = BeautifulSoup(html, "html.parser")
        out: list[dict] = []
        for res in soup.select("div.result, div.web-result")[: max_results * 2]:
            a = res.select_one("a.result__a")
            if not a:
                continue
            url = _decode_ddg_href(a.get("href", ""))
            if not url.startswith("http"):
                continue
            snippet_el = res.select_one(".result__snippet")
            out.append({
                "title": a.get_text(strip=True),
                "url": url,
                "snippet": (snippet_el.get_text(strip=True) if snippet_el else "")[:300],
            })
            if len(out) >= max_results:
                break
        return out

    return _run_blocking(_do)


def local_search(query: str, max_results: int = 5) -> list[dict]:
    """Free web search via local headless browser. Returns [{title,url,snippet}].
    Tries Playwright, then httpx+BS4, then []. Never raises."""
    query = (query or "").strip()
    if not query:
        return []
    for name, fn in (("playwright", _search_playwright), ("httpx", _search_httpx)):
        try:
            results = fn(query, max_results)
            if results:
                log_event(logger, "local_search_ok", engine=name, query_chars=len(query), results=len(results))
                return results
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "local_search_failed", engine=name, error=str(exc)[:160])
    return []


# ── Scrape: httpx fallback ───────────────────────────────────────────────────
def _scrape_httpx(url: str) -> dict:
    import httpx

    resp = httpx.get(url, headers=_headers(), timeout=settings.WEB_FETCH_TIMEOUT_SECONDS,
                     follow_redirects=True)
    resp.raise_for_status()
    return clean_html(resp.text, url)


# ── Scrape: Playwright ───────────────────────────────────────────────────────
def _scrape_playwright(url: str) -> dict:
    from playwright.sync_api import sync_playwright  # lazy

    def _do() -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.BROWSER_HEADLESS)
            try:
                ctx = browser.new_context(
                    user_agent=settings.WEB_USER_AGENT,
                    locale="en-US",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded",
                          timeout=settings.BROWSER_NAV_TIMEOUT_MS)
                return page.content()
            finally:
                browser.close()

    html = _run_blocking(_do)
    return clean_html(html, url)


def scrape_url(url: str) -> dict:
    """Visit `url` headlessly and return {url, title, text, markdown} with
    scripts/CSS/nav stripped. Tries Playwright, then httpx+BS4. Never raises —
    returns an empty-text dict on total failure."""
    url = (url or "").strip()
    if not url.startswith("http"):
        return {"url": url, "title": "", "text": "", "markdown": "", "error": "invalid_url"}
    for name, fn in (("playwright", _scrape_playwright), ("httpx", _scrape_httpx)):
        try:
            data = fn(url)
            if data.get("text"):
                log_event(logger, "scrape_ok", engine=name, url=url[:120], chars=len(data["text"]))
                return {"url": url, **data}
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "scrape_failed", engine=name, url=url[:120], error=str(exc)[:160])
    return {"url": url, "title": "", "text": "", "markdown": "", "error": "unreachable"}


def browser_available() -> bool:
    """True when Playwright + a Chromium build are installed (for diagnostics)."""
    try:
        from playwright.sync_api import sync_playwright

        def _probe() -> bool:
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                b.close()
            return True

        return bool(_run_blocking(_probe))
    except Exception:  # noqa: BLE001
        return False
