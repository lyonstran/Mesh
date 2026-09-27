from pydantic import BaseModel

from app.ai.provider import LLMError


class MockProvider:
    """Deterministic stand-in so the app runs with no API key (PLAN.md §14.11).

    complete_text echoes the user text, which makes embedding normalization a no-op. Callers skip
    complete_json under mock and use their keyword-rule output instead (e.g. services/triage.py).
    """

    name = "mock"

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str:
        return user

    async def complete_json[M: BaseModel](self, system: str, user: str, schema: type[M], temperature: float = 0.2) -> M:
        raise LLMError("MockProvider has no structured output; use the rules result")
