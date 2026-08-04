"""Tests for the classifier + ignore filter."""

from university_intel.classifier import classify, process, should_publish


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
