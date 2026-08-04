"""Pluggable semantic similarity for title-level deduplication.

Default provider is `local` — free, offline, token-normalised fuzzy matching
via RapidFuzz. An optional `grok` provider uses xAI's embeddings endpoint
(SEMANTIC_PROVIDER=grok + GROK_API_KEY) when you want real embeddings; it falls
back to the local scorer if the API is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import re

from rapidfuzz import fuzz

from university_intel.config import GROK_API_KEY, SEMANTIC_PROVIDER

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> str:
    """Lowercase alphanumeric tokens joined by spaces (stopwords kept)."""
    return " ".join(_WORD_RE.findall((text or "").lower()))


class SemanticScorer:
    async def similarity(self, a: str, b: str) -> float:
        raise NotImplementedError


class LocalFuzzyScorer(SemanticScorer):
    """RapidFuzz similarity over token-normalised titles."""

    async def similarity(self, a: str, b: str) -> float:
        ta, tb = _tokens(a), _tokens(b)
        if not ta or not tb:
            return 0.0
        return max(
            fuzz.ratio(ta, tb) / 100.0,
            fuzz.token_set_ratio(ta, tb) / 100.0,
        )


class GrokScorer(SemanticScorer):
    """Optional embeddings-based scorer via xAI (OpenAI-compatible API)."""

    _EMBEDDING_URL = "https://api.x.ai/v1/embeddings"
    _MODEL = "grok-embedding-1"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("GROK_API_KEY is required for the grok scorer")
        self._api_key = api_key
        self._fallback = LocalFuzzyScorer()
        self._cache: dict[str, list[float]] = {}

    async def _embed(self, text: str) -> list[float]:
        import aiohttp

        if text in self._cache:
            return self._cache[text]
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._EMBEDDING_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._MODEL, "input": text},
                timeout=30,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"embedding API error {resp.status}")
                data = await resp.json()
        vector = data["data"][0]["embedding"]
        self._cache[text] = vector
        return vector

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    async def similarity(self, a: str, b: str) -> float:
        try:
            va, vb = await asyncio.gather(self._embed(a), self._embed(b))
            return self._cosine(va, vb)
        except Exception as exc:
            logger.warning("grok scorer failed, falling back to local: %s", exc)
            return await self._fallback.similarity(a, b)


def get_scorer() -> SemanticScorer:
    if SEMANTIC_PROVIDER == "grok":
        try:
            return GrokScorer(GROK_API_KEY)
        except ValueError as exc:
            logger.warning("grok scorer unavailable: %s — using local", exc)
    return LocalFuzzyScorer()
