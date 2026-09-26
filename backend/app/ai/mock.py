class MockProvider:
    """Deterministic stand-in so the app runs with no API key (PLAN.md §14.11).

    complete_text echoes the user text, which makes embedding normalization a no-op.
    """

    name = "mock"

    async def complete_text(self, system: str, user: str, temperature: float = 0.3) -> str:
        return user
