"""Tests for the semantic scorer."""

import asyncio

from university_intel.semantic import LocalFuzzyScorer, get_scorer


def test_local_scorer_similar_titles():
    scorer = LocalFuzzyScorer()
    sim = asyncio.run(
        scorer.similarity(
            "National Hackathon 2026 Registration Open",
            "National Hackathon 2026 Registration Open!",
        )
    )
    assert sim > 0.9


def test_local_scorer_dissimilar_titles():
    scorer = LocalFuzzyScorer()
    sim = asyncio.run(
        scorer.similarity(
            "AI Workshop on Transformers",
            "Tender for Canteen Services",
        )
    )
    assert sim < 0.5


def test_get_scorer_defaults_to_local(monkeypatch):
    monkeypatch.setattr("university_intel.semantic.SEMANTIC_PROVIDER", "local")
    assert isinstance(get_scorer(), LocalFuzzyScorer)


def test_get_scorer_falls_back_when_grok_misconfigured(monkeypatch):
    monkeypatch.setattr("university_intel.semantic.SEMANTIC_PROVIDER", "grok")
    monkeypatch.setattr("university_intel.semantic.GROK_API_KEY", "")
    assert isinstance(get_scorer(), LocalFuzzyScorer)
