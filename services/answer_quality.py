"""Flags bot replies that didn't actually answer, so owners can fill the gaps."""
import re
from typing import Optional

ANSWERED = "answered"
UNANSWERED = "unanswered"
HANDOFF = "handoff"
# Owner-set states
CORRECTED = "corrected"
DISMISSED = "dismissed"

# Phrases models use when the knowledge base has nothing on the topic
_REFUSAL_RE = re.compile(
    r"\b("
    r"i (?:do not|don't|don’t) (?:have|know|see|find)"
    r"|i(?:'m| am) (?:not sure|unable|not able|afraid i)"
    r"|i (?:can(?:no|')t|could(?:n't| not)) (?:find|answer|help with|provide|locate)"
    r"|(?:no|not any) (?:information|details|mention|data) (?:about|on|regarding|available)"
    r"|(?:isn't|is not|wasn't|was not) (?:mentioned|covered|included|available) in"
    r"|outside (?:of )?(?:my|the) (?:knowledge|scope)"
    r"|(?:contact|reach out to) (?:our |the )?support"
    r")",
    re.IGNORECASE,
)


def looks_unanswered(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return True
    # Long answers that merely *mention* support are usually real answers
    head = text[:280]
    return bool(_REFUSAL_RE.search(head))


def classify_answer(answer: str, *, retrieval_used: bool, context: str, handoff: bool) -> str:
    if handoff:
        return HANDOFF
    if looks_unanswered(answer):
        return UNANSWERED
    if retrieval_used and not (context or "").strip() and len((answer or "").strip()) < 400:
        # Nothing retrieved: short replies here are usually generic deflections
        return UNANSWERED
    return ANSWERED


def normalize_question(text: Optional[str]) -> str:
    """Grouping key so 'What are your hours?' and 'what are your hours' land together."""
    value = (text or "").lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:200]
