"""AI triage merged over the keyword rules (PLAN.md §9.2).

The LLM classifies and summarizes; the rules set a floor it can never go below (CLAUDE.md rules 3 and 4).
When the LLM is off, slow or wrong, the rules alone produce the card, so a request is never blocked.
"""

import asyncio
import logging

from pydantic import BaseModel, Field, field_validator

from app.ai import prompts
from app.ai.provider import LLMError, get_provider
from app.models import Category, Triage, TriageFlag
from app.services.rules import RuleResult

log = logging.getLogger("mesh.triage")

# The requester waits on the preview. Spark answers in ~5-8 s, so allow one slow reply, then use the rules.
TIMEOUT_S = 15
FALLBACK_SUMMARY_CHARS = 120
MAX_NEEDS = 5


class TriageOutput(BaseModel):
    """What the LLM must return. Lenient on extras the prompt didn't ask for, strict on urgency."""

    category: Category
    urgency: int = Field(ge=1, le=5)
    flags: list[TriageFlag] = []
    needs: list[str] = []
    summary: str = Field(min_length=1)
    language: str = "en"

    @field_validator("category", mode="before")
    @classmethod
    def _unknown_category_is_other(cls, value: object) -> object:
        return value if value in Category.__members__.values() else Category.other

    @field_validator("flags", mode="before")
    @classmethod
    def _drop_unknown_flags(cls, value: object) -> object:
        return [f for f in value if f in TriageFlag.__members__.values()] if isinstance(value, list) else value

    @field_validator("needs")
    @classmethod
    def _tidy_needs(cls, value: list[str]) -> list[str]:
        return [n.strip()[:80] for n in value if n.strip()][:MAX_NEEDS]

    @field_validator("summary")
    @classmethod
    def _cap_summary(cls, value: str) -> str:
        return value.strip()[:200]

    @field_validator("language")
    @classmethod
    def _tidy_language(cls, value: str) -> str:
        return value.strip().lower()[:10] or "en"


def merge(rule: RuleResult, llm: TriageOutput | None, text: str, language: str) -> Triage:
    """Combine rules and LLM output. Urgency = max(floor, llm); flags = union; no LLM → rules only."""
    if llm is None:
        return Triage(
            category=rule.category or Category.other,
            urgency=rule.floor,
            urgency_rule_floor=rule.floor,
            emergency=rule.emergency,
            flags=sorted(rule.flags),
            needs=[],
            summary=text.strip()[:FALLBACK_SUMMARY_CHARS],
            language=language,
            source="rules",
        )
    return Triage(
        category=llm.category,
        urgency=max(rule.floor, llm.urgency),
        urgency_rule_floor=rule.floor,
        emergency=rule.emergency,  # only the rules decide this, so it holds when the LLM is down
        flags=sorted(rule.flags | set(llm.flags)),
        needs=llm.needs,
        summary=llm.summary,
        language=llm.language,
        source="ai",
    )


def apply_category_override(result: Triage, category: Category | None) -> Triage:
    """The requester may correct the category on the preview card. Urgency, the floor and flags don't change."""
    return result if category is None else result.model_copy(update={"category": category})


async def triage(text: str, hazard_types: list[str], rule_result: RuleResult, *, language: str = "en") -> Triage:
    """Triage a request. Never raises: any LLM failure falls back to the rules result."""
    provider = get_provider()
    if provider.name == "mock":
        return merge(rule_result, None, text, language)
    try:
        llm = await asyncio.wait_for(
            provider.complete_json(prompts.TRIAGE, prompts.triage_input(text, hazard_types), TriageOutput),
            timeout=TIMEOUT_S,
        )
    except (LLMError, TimeoutError) as e:
        log.warning("Triage LLM unavailable (%s); using rules only", type(e).__name__)
        llm = None
    except Exception:
        log.exception("Triage LLM failed unexpectedly; using rules only")
        llm = None
    return merge(rule_result, llm, text, language)
