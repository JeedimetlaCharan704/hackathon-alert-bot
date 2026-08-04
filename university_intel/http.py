"""Async HTTP client for University Intelligence.

Uses aiohttp. Respects a configurable politeness delay between requests and
retries transient failures with exponential backoff. Only fetches public pages
and never ignores robots-style etiquette beyond the standard delay.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urljoin, urlparse

import aiohttp

from university_intel.config import (
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    SCAN_ALLOWED_HOSTS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (aiohttp.ClientError, asyncio.TimeoutError, OSError)


class HttpError(Exception):
    pass


class AsyncHttp:
    """A single session + a shared politeness gate."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._last_request = 0.0
        self._lock = asyncio.Lock()
        self._allowed_hosts: set[str] | None = None
        if SCAN_ALLOWED_HOSTS:
            self._allowed_hosts = {
                h.strip().lower() for h in SCAN_ALLOWED_HOSTS.split(",") if h.strip()
            }

    async def start(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("AsyncHttp.start() must be called first")
        return self._session

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < REQUEST_DELAY_SECONDS:
                await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
            self._last_request = time.monotonic()

    def _allowed(self, url: str) -> bool:
        if self._allowed_hosts is None:
            return True
        return urlparse(url).netloc.lower() in self._allowed_hosts

    async def fetch(self, url: str, *, as_json: bool = False) -> str | dict:
        """GET a public URL, honouring the delay + retries. Raises HttpError."""
        if not self._allowed(url):
            raise HttpError(f"host not in SCAN_ALLOWED_HOSTS: {url}")

        attempt = 0
        while True:
            attempt += 1
            await self._throttle()
            try:
                async with self.session.get(url, allow_redirects=True) as resp:
                    if resp.status == 404:
                        raise HttpError(f"404 Not Found: {url}")
                    if resp.status >= 400:
                        raise HttpError(f"HTTP {resp.status}: {url}")
                    if as_json:
                        return await resp.json(content_type=None)
                    return await resp.text()
            except _RETRYABLE as exc:
                if attempt >= RETRY_ATTEMPTS:
                    raise HttpError(f"failed after {attempt} tries: {url} ({exc})")
                wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Retry %d/%d for %s after %.1fs (%s)",
                    attempt,
                    RETRY_ATTEMPTS,
                    url,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

    def absolute_url(self, base: str, href: str) -> str | None:
        """Resolve a possibly-relative href against base into an absolute http(s) URL."""
        href = (href or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return None
        resolved = urljoin(base, href)
        if resolved.lower().startswith(("http://", "https://")):
            return resolved
        return None
