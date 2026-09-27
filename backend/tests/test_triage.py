"""Triage: rules floor, LLM merge and fallbacks (PLAN.md §9.2). No database or API key needed."""

import asyncio
import itertools

import pytest

from app.ai import provider as provider_module
from app.ai.provider import LLMError, TriageFallback, complete_json_via_text, parse_json
from app.models import Category, TriageFlag
from app.services import triage as triage_module
from app.services.rules import RuleResult, urgency_floor, rule_category
from app.services.triage import TriageOutput, apply_category_override, merge, triage

TEXT = "A tree fell across my driveway and I can't get my car out."


def _llm(urgency: int = 2, **fields) -> TriageOutput:
    return TriageOutput(**({"category": "debris", "urgency": urgency, "summary": "Tree blocking driveway"} | fields))


def _rule(floor: int = 1, emergency: bool = False, flags=(), category=Category.debris) -> RuleResult:
    return RuleResult(floor=floor, emergency=emergency, flags=frozenset(flags), category=category)


class FakeProvider:
    """Stands in for Muse: returns a fixed reply, raises, or hangs."""

    name = "fake"

    def __init__(self, reply=None, error: Exception | None = None, delay: float = 0) -> None:
        self.reply, self.error, self.delay, self.calls = reply, error, delay, 0

    async def complete_text(self, system, user, temperature=0.3):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply[min(self.calls, len(self.reply)) - 1] if isinstance(self.reply, list) else self.reply

    async def complete_json(self, system, user, schema, temperature=0.2):
        return await complete_json_via_text(self.complete_text, system, user, schema, temperature)


@pytest.fixture
def use_provider(monkeypatch):
    def install(fake):
        monkeypatch.setattr(triage_module, "get_provider", lambda: fake)
        return fake

    return install


# --- the LLM can never lower urgency ---------------------------------------------


@pytest.mark.parametrize(("floor", "llm_urgency"), list(itertools.product(range(1, 6), range(1, 6))))
def test_urgency_is_max_of_floor_and_llm(floor, llm_urgency):
    result = merge(_rule(floor), _llm(llm_urgency), TEXT, "en")
    assert result.urgency == max(floor, llm_urgency)
    assert result.urgency >= floor
    assert result.urgency_rule_floor == floor


def test_flags_are_the_union():
    result = merge(_rule(4, flags=[TriageFlag.medical_device]), _llm(flags=["elderly"]), TEXT, "en")
    assert result.flags == [TriageFlag.elderly, TriageFlag.medical_device]


def test_llm_cannot_clear_emergency():
    result = merge(_rule(5, emergency=True), _llm(1), "no puedo respirar", "es")
    assert result.emergency and result.urgency == 5


@pytest.mark.parametrize("category", list(Category))
def test_category_override_never_changes_urgency(category):
    original = merge(_rule(4, flags=[TriageFlag.medical_device]), _llm(5), TEXT, "en")
    overridden = apply_category_override(original, category)
    assert overridden.category == category
    assert (overridden.urgency, overridden.urgency_rule_floor, overridden.flags) == (5, 4, original.flags)


def test_no_override_keeps_the_card():
    card = merge(_rule(), _llm(), TEXT, "en")
    assert apply_category_override(card, None) == card


# --- fallback: the provider down never blocks a request ---------------------------


async def test_provider_error_falls_back_to_rules(use_provider):
    use_provider(FakeProvider(error=LLMError("Muse returned 503")))
    result = await triage(TEXT, [], urgency_floor(TEXT), language="en")
    assert result.source == "rules"
    assert result.category == Category.debris
    assert result.summary == TEXT[:120]


async def test_fallback_summary_is_first_120_characters(use_provider):
    use_provider(FakeProvider(error=LLMError("down")))
    long_text = "Our street is flooded and " + "x" * 300
    assert (await triage(long_text, [], urgency_floor(long_text))).summary == long_text[:120]


async def test_no_matching_rule_falls_back_to_other(use_provider):
    use_provider(FakeProvider(error=LLMError("down")))
    assert (await triage("Can someone help me please", [], urgency_floor("Can someone help me please"))).category == Category.other


async def test_slow_provider_times_out_to_rules(use_provider, monkeypatch):
    monkeypatch.setattr(triage_module, "TIMEOUT_S", 0.05)
    use_provider(FakeProvider(reply="{}", delay=1))
    assert (await triage(TEXT, [], urgency_floor(TEXT))).source == "rules"


async def test_invalid_json_twice_falls_back(use_provider):
    fake = use_provider(FakeProvider(reply="Sure! It's a tree problem."))
    assert (await triage(TEXT, [], urgency_floor(TEXT))).source == "rules"
    assert fake.calls == 2  # one retry, then give up


async def test_invalid_json_then_valid_uses_the_retry(use_provider):
    good = '{"category": "debris", "urgency": 2, "flags": [], "needs": ["tree removal"], "summary": "Tree on driveway", "language": "en"}'
    fake = use_provider(FakeProvider(reply=["not json", good]))
    result = await triage(TEXT, [], urgency_floor(TEXT))
    assert result.source == "ai" and result.needs == ["tree removal"]
    assert fake.calls == 2


async def test_unexpected_exception_still_falls_back(use_provider):
    use_provider(FakeProvider(error=RuntimeError("bug")))
    assert (await triage(TEXT, [], urgency_floor(TEXT))).source == "rules"


async def test_mock_provider_uses_rules_without_calling_an_llm():
    # conftest pins LLM_PROVIDER=mock
    result = await triage(TEXT, [], urgency_floor(TEXT))
    assert result.source == "rules" and result.category == Category.debris


@pytest.mark.parametrize("text", ["My dad can't breathe", "no puedo respirar", "my neighbor is trapped"])
async def test_emergency_phrases_hold_with_the_llm_down(use_provider, text):
    use_provider(FakeProvider(error=LLMError("down")))
    result = await triage(text, [], urgency_floor(text))
    assert result.emergency and result.urgency == 5


async def test_llm_output_that_lowers_urgency_is_raised_back(use_provider):
    reply = '{"category": "power", "urgency": 1, "flags": [], "needs": [], "summary": "Needs power", "language": "en"}'
    use_provider(FakeProvider(reply=reply))
    text = "My oxygen concentrator needs power."
    result = await triage(text, [], urgency_floor(text, {"medical_device": True}))
    assert result.source == "ai" and result.urgency == 4


# --- JSON parsing --------------------------------------------------------------------


def test_parse_json_strips_code_fences_and_chatter():
    raw = 'Here you go:\n```json\n{"category": "water", "urgency": 3, "summary": "Needs water"}\n```'
    out = parse_json(raw, TriageOutput)
    assert out.category == Category.water and out.urgency == 3


def test_unknown_category_and_flags_are_tolerated():
    out = parse_json('{"category": "flooding", "urgency": 2, "flags": ["elderly", "pets"], "summary": "x"}', TriageOutput)
    assert out.category == Category.other and out.flags == [TriageFlag.elderly]


@pytest.mark.parametrize("urgency", [0, 6, "high"])
def test_out_of_range_urgency_is_rejected(urgency):
    with pytest.raises(ValueError):
        parse_json(f'{{"category": "water", "urgency": {urgency!r}, "summary": "x"}}'.replace("'", '"'), TriageOutput)


async def test_complete_json_raises_triage_fallback():
    with pytest.raises(TriageFallback):
        await complete_json_via_text(FakeProvider(reply="nope").complete_text, "s", "u", TriageOutput, 0.2)


def test_mock_is_the_default_provider():
    assert provider_module.get_provider().name == "mock"


# --- rules ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("A tree fell across my driveway and I can't get my car out.", Category.debris),
        ("My oxygen concentrator needs power. The electricity has been out since last night.", Category.power),
        ("Necesito que alguien me lleve al refugio, no tengo carro.", Category.transport),
        ("My elderly neighbor lives alone and hasn't answered her door since the storm.", Category.welfare_check),
        ("We're running low on drinking water and food for two kids.", Category.water),
        ("I'm out of insulin", Category.medical_supplies),
        ("Necesitamos pañales y pilas", Category.supplies),
        ("It's freezing and we have no heat", Category.warming),
    ],
)
def test_rule_category(text, category):
    assert rule_category(text) == category


def test_requester_flags_raise_the_floor():
    assert urgency_floor("need water").floor == 1
    assert urgency_floor("need water", {"mobility": True}).floor == 3
    assert urgency_floor("need water", {"lives_alone": True, "medical_device": True}).floor == 4
    assert urgency_floor("need water", {"medical_device": True}).flags == {TriageFlag.medical_device}


def test_emergency_sets_floor_five():
    result = urgency_floor("hay un incendio")
    assert result.emergency and result.floor == 5
