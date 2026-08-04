"""Tests for the classifier + ignore filter."""

from university_intel.classifier import (
    PRIZE_CATEGORIES,
    classify,
    mentions_prize,
    process,
    should_publish,
)


def test_opportunities_classified():
    assert process("National Hackathon 2026 - Register Now") == "Hackathon"
    assert process("Freshers Coding Contest") == "Coding Contest"
    assert process("Startup Challenge by IIC") == "Startup Challenge"
    assert process("AI & ML Workshop") == "Workshop"
    assert process("Summer Research Internship") == "Internship"
    assert process("Merit Scholarship 2026") == "Scholarship"
    assert process("National Conference on AI") == "Conference"
    assert process("Tech Fest 2026") == "Tech Fest"
    assert process("Innovation Challenge by Innovation Cell") == "Innovation Challenge"
    assert process("Research Paper Presentation Competition") == "Research Competition"
    assert process("5-Day Bootcamp on Full Stack") == "Bootcamp"
    assert process("Seed Grant for Student Startups") == "Grant"
    assert process("Ideathon - Idea Contest") == "Ideathon"


def test_ignore_list_drops_noise():
    for title in (
        "Admission Notice 2026-27",
        "Mid-term Examination Schedule",
        "Results declared for B.Tech III year",
        "Tender for campus canteen",
        "Recruitment of Assistant Professors",
        "Office Order - Internal Assessment",
        "Holiday on account of festival",
        "General Circular for all departments",
        "Hall ticket download for end semester exams",
    ):
        assert process(title, "") is None, f"should drop: {title}"


def test_should_publish_allow_opportunity_in_body():
    # "notice" in the body should not kill an obvious opportunity.
    assert should_publish("Hackathon 2026", "Hackathon notice for students") is True


def test_should_publish_drops_body_noise_when_not_opportunity():
    assert should_publish("College update", "This is a general circular") is False


def test_classify_unknown_is_other():
    assert classify("Some random announcement about library timings") == "Other"


def test_mentions_prize_detects_prize_text():
    assert mentions_prize("National Ideathon with cash prize of Rs. 50,000") is True
    assert mentions_prize("Workshop", "Winners get a cash prize of ₹1 Lakh") is True
    assert mentions_prize("Paper Presentation Contest", "Best paper awarded $500") is True
    assert mentions_prize("Hackathon", "Prize pool worth Rs. 2,00,000") is True


def test_mentions_prize_false_for_plain_events():
    assert mentions_prize("National Conference on AI") is False
    assert mentions_prize("Workshop on RAG to Reality") is False
    assert mentions_prize("5-Day Bootcamp on Full Stack") is False
    assert mentions_prize("Scholarship awareness program") is False


def test_prize_categories_pass_without_prize_text():
    for category in PRIZE_CATEGORIES:
        assert category != ""
    assert "Hackathon" in PRIZE_CATEGORIES
    assert "Coding Contest" in PRIZE_CATEGORIES
    assert "Workshop" not in PRIZE_CATEGORIES
    assert "Conference" not in PRIZE_CATEGORIES
