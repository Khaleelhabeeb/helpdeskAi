import pytest

from services.answer_quality import (
    ANSWERED, HANDOFF, UNANSWERED, classify_answer, looks_unanswered, normalize_question,
)


@pytest.mark.parametrize("text", [
    "I don't have information about that.",
    "I'm not sure about the warranty terms.",
    "Sorry, I couldn't find anything on international shipping.",
    "That isn't mentioned in our documentation.",
    "",
])
def test_refusals_flagged(text):
    assert looks_unanswered(text)


@pytest.mark.parametrize("text", [
    "We're open 9am–5pm, Monday to Friday.",
    "Refunds are available within 30 days of purchase.",
])
def test_real_answers_not_flagged(text):
    assert not looks_unanswered(text)


def test_classify_priorities():
    assert classify_answer("anything", retrieval_used=True, context="", handoff=True) == HANDOFF
    assert classify_answer("Our hours are 9–5.", retrieval_used=True, context="", handoff=False) == UNANSWERED
    assert classify_answer("Our hours are 9–5.", retrieval_used=True, context="hours: 9-5", handoff=False) == ANSWERED
    assert classify_answer("Our hours are 9–5.", retrieval_used=False, context="", handoff=False) == ANSWERED


def test_normalize_groups_variants():
    assert normalize_question("What are your HOURS?") == normalize_question("what are your hours")
    assert normalize_question("<user_query>Hi!</user_query>") == "hi"
