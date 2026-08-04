"""Rule-based classification + relevance filter (the "AI filter").

Two jobs:

1. *Ignore filter* — drop admissions, exam schedules, holiday notices, results,
   tenders, recruitment, and general circulars. Only student-relevant
   opportunities pass.
2. *Classifier* — label surviving announcements with one of the 15 categories.

Everything is deterministic, offline, and cheap. No LLM calls are required for
normal operation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ignore filter
# ---------------------------------------------------------------------------

# Matches the *title* alone → drop immediately.
_IGNORE_TITLE_RE = re.compile(
    r"\b(admission|admissions|admission\s+notice|admission\s+schedule|"
    r"entrance\s+exam|entrance\s+test|hall\s+ticket|admit\s+card|exam\s+schedule|"
    r"examination\s+schedule|time\s*table|timetable|exam\s+time|exam\s+fee|"
    r"mid[-\s]*term|end[-\s]*semester|supplementary\s+exam|results?|result\s+declared|"
    r"rank\s+list|merit\s+list|counselling|counseling|seat\s+allocation|"
    r"holiday|declared\s+holiday|leave\s+application|reopening|re-open|"
    r"reopening\s+of\s+college|vacation\s+schedule|"
    r"tender|tenders|eoi\b|expression\s+of\s+interest|quotation|auction|"
    r"recruitment|vacanc|walk[- ]in\s+interview|faculty\s+recruitment|"
    r"staff\s+selection|job\s+opening|job\s+notification|notification\s+for\s+post|"
    r"office\s+order|g\.?o\.?\s*(no)?\.?\s*\d|government\s+order|"
    r"circular|general\s+circular|press\s+release|"
    r"board\s+of\s+studies|b\.o\.s\.|exam\s+branch|student\s+registration\s+for\s+exam|"
    r"annual\s+day|convocation\s+ceremony|fee\s+payment|fees\s+structure|"
    r"anti[-\s]*ragging|hostel\s+allotment|transport\s+rules|election\s+notification)\b",
    re.IGNORECASE,
)

# Matches in title *or* description → still dropped, but only if the text isn't
# clearly about an opportunity (avoids nuking "Internship" etc.).
_IGNORE_BODY_RE = re.compile(
    r"\b(admission|examination\s+schedule|exam\s+schedule|holiday\s+notice|"
    r"tender\s+notice|recruitment\s+notice|staff\s+vacancy|office\s+order|"
    r"results?\s+declared|internal\s+assessment|supplementary\s+examination|"
    r"general\s+circular|circular\s+for)\b",
    re.IGNORECASE,
)

# Text that strongly indicates a real opportunity — if it is present we will not
# drop on body-only ignore matches.
_OPPORTUNITY_RE = re.compile(
    r"\b(hackathon|ideathon|workshop|bootcamp|conference|symposium|summit|"
    r"contest|competition|challenge|internship|scholarship|fellowship|grant|"
    r"tech\s*fest|startup|pitch|incubation|innovation|conclave|congress|"
    r"research|hack\b|code|programming|coding|ai\b|ml\b|data\s*science|"
    r"paper\s+presentation)\b",
    re.IGNORECASE,
)

# Prize-money signals. If any of these appear in the title or description the
# announcement is treated as a prize-bearing opportunity.
_PRIZE_WORD_RE = re.compile(
    r"\b(cash\s+prize|prize\s+money|prize\s+pool|prize\s+amount|prizes?|"
    r"reward|winner\s+gets|win\s+upto|winning\s+amount|incentive|"
    r"award\s+of|worth\s+rs\.?|worth\s+₹|worth\s+\$)\b",
    re.IGNORECASE,
)
# Currency / money-amount markers (₹, Rs., Lakh, Crore, $, USD, INR, ...).
_PRIZE_CURRENCY_RE = re.compile(
    r"(₹|rs\.?\s*\d|rupees|lakhs?|lacs?|crores?|"
    r"\$\s*\d|\b\d+\s*(lakh|lac|crore)\b|usd\b|inr\b|euros?|€)",
    re.IGNORECASE,
)

# Categories whose events normally award prizes to winners — these pass the
# prize filter even when no amount is written on the announcement itself.
PRIZE_CATEGORIES = {
    "Hackathon",
    "Coding Contest",
    "Ideathon",
    "Startup Challenge",
    "Innovation Challenge",
    "AI Competition",
    "Research Competition",
}


def mentions_prize(title: str, description: str = "") -> bool:
    """True if the text mentions a cash prize / reward (money marker present)."""
    text = f"{title or ''} {description or ''}"[:4000]
    return bool(_PRIZE_WORD_RE.search(text) or _PRIZE_CURRENCY_RE.search(text))


def title_has_signal(title: str) -> bool:
    """True if the title itself points at a student opportunity."""
    return bool(title and _OPPORTUNITY_RE.search(title))


def should_publish(title: str, description: str = "") -> bool:
    """Return False for irrelevant university notices."""
    title = title or ""
    desc = (description or "")[:2000]
    if _IGNORE_TITLE_RE.search(title):
        return False
    if _OPPORTUNITY_RE.search(title):
        return True
    if _IGNORE_BODY_RE.search(title):
        return False
    if _IGNORE_BODY_RE.search(desc) and not _OPPORTUNITY_RE.search(desc):
        return False
    return True


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Rule:
    category: str
    phrases: tuple[str, ...] = ()
    words: tuple[str, ...] = ()
    weight: int = 1


_RULES: tuple[_Rule, ...] = (
    _Rule("Hackathon", phrases=("hackathon",), words=()),
    _Rule("Coding Contest", phrases=(
        "coding contest", "coding competition", "programming contest",
        "competitive programming", "coding challenge", "code challenge",
        "cp contest", "dsa contest", "coding event", "code contest",
        "problem solving contest",
    ), words=("code", "coding", "programming", "leetcode")),
    _Rule("Ideathon", phrases=("ideathon", "idea contest", "idea competition"), words=()),
    _Rule("AI Competition", phrases=(
        "ai competition", "ai contest", "ml competition", "ai challenge",
        "ml challenge", "machine learning competition", "data science competition",
        "data science challenge", "deep learning contest", "genai challenge",
        "ai hackathon",
    ), words=("ai", "ml", "llm", "genai", "deep learning")),
    _Rule("Innovation Challenge", phrases=(
        "innovation challenge", "innovation contest", "innovation competition",
        "innovation award", "smart india", "innovation challenge",
    ), words=("innovation",)),
    _Rule("Startup Challenge", phrases=(
        "startup challenge", "startup competition", "startup hunt",
        "business plan", "pitch", "pitch competition", "startup weekend",
        "entrepreneur competition", "funding challenge", "startup showcase",
    ), words=("startup", "entrepreneur", "incubation")),
    _Rule("Research Competition", phrases=(
        "research competition", "research contest", "research challenge",
        "paper presentation", "research paper", "poster competition",
        "research poster", "student research", "project competition",
    ), words=("research",)),
    _Rule("Workshop", phrases=(
        "hands-on workshop", "technical workshop", "skill workshop",
        "workshop", "masterclass", "hands-on session",
    ), words=()),
    _Rule("Bootcamp", phrases=(
        "bootcamp", "boot camp", "immersive program", "summer bootcamp",
    ), words=()),
    _Rule("Internship", phrases=(
        "internship", "internship program", "summer internship",
        "research internship", "paid internship", "intern",
    ), words=()),
    _Rule("Grant", phrases=(
        "research grant", "seed grant", "seed fund", "startup grant",
        "grant", "funding opportunity", "financial support", "prize money grant",
    ), words=()),
    _Rule("Scholarship", phrases=(
        "scholarship", "scholarship program", "fellowship",
        "stipend", "financial aid", "merit scholarship",
    ), words=()),
    _Rule("Conference", phrases=(
        "national conference", "international conference", "conference",
        "symposium", "tech summit", "summit", "congress", "conclave",
    ), words=()),
    _Rule("Tech Fest", phrases=(
        "tech fest", "techfest", "techno cultural fest", "technical fest",
        "annual tech fest", "college fest",
    ), words=("fest",)),
    _Rule("Other", phrases=(), words=()),
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def classify(title: str, description: str = "") -> str:
    """Label text with one of the 15 categories (deterministic)."""
    text = f"{title or ''} {description or ''}"[:4000].lower()
    best, best_score = "Other", 0
    for rule in _RULES:
        if rule.category == "Other":
            continue
        score = 0
        for phrase in rule.phrases:
            if phrase in text:
                score += 3 * rule.weight
        for word in rule.words:
            if re.search(rf"\b{re.escape(word)}\b", text):
                score += 1 * rule.weight
        if score > best_score:
            best, best_score = rule.category, score
    return best


def process(title: str, description: str = "") -> str | None:
    """Return the category if the announcement should be published, else None."""
    if not should_publish(title, description):
        return None
    return classify(title, description)
