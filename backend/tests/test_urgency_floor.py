"""rules.urgency_floor, the P1 contract (PLAN.md §9.2 step 1). No LLM, no database."""

import pytest

from app.models import TriageFlag as F
from app.services.rules import urgency_floor


@pytest.mark.parametrize(
    "text, flag",
    [
        ("My mother is on oxygen and the power is out", F.medical_device),
        ("Our oxygen concentrator needs power", F.medical_device),
        ("I missed dialysis because the roads flooded", F.medical_device),
        ("My insulin needs to stay cold", F.medical_device),
        ("He is on a ventilator at home", F.medical_device),
        ("Mi mamá usa oxígeno y no hay luz", F.medical_device),
        ("Necesito ir a diálisis mañana", F.medical_device),
        ("Mi insulina necesita refrigeración", F.medical_device),
        ("Mi papá usa un respirador", F.medical_device),
        ("I use a wheelchair and the ramp is blocked", F.mobility),
        ("My husband is bedridden", F.mobility),
        ("Uso silla de ruedas y la rampa está bloqueada", F.mobility),
        ("Mi esposo está encamado", F.mobility),
        ("We have an infant and no formula", F.infant),
        ("I have a baby and no clean water", F.infant),
        ("Tengo un bebé y no tengo agua", F.infant),
        ("Tengo un recién nacido", F.infant),
    ],
)
def test_high_terms_set_floor_four_with_their_flag(text, flag):
    result = urgency_floor(text)
    assert result.floor == 4 and flag in result.flags and not result.emergency


@pytest.mark.parametrize(
    "text",
    [
        "My elderly neighbor is alone and the power is out",
        "My grandmother lives by herself and hasn't answered",
        "I'm 84 and alone in the house",
        "Mi abuela vive sola y no tiene luz",
        "Un anciano está solo en su casa",
    ],
)
def test_elderly_alone_sets_floor_four(text):
    result = urgency_floor(text)
    assert result.floor == 4 and {F.elderly, F.lives_alone} <= result.flags


@pytest.mark.parametrize(
    "text",
    [
        "A tree fell across my driveway",
        "Necesito un ventilador, hace mucho calor",  # "ventilador" alone means a fan
        "We need a babysitter? No, just water",
        "I left the dog alone. My grandma called later.",  # older person and "alone" in different sentences
        "My 12 year old is home alone",  # alone, but not an older person
    ],
)
def test_ordinary_requests_stay_at_one(text):
    result = urgency_floor(text)
    assert result.floor == 1 and not result.flags


@pytest.mark.parametrize(
    "flags, floor",
    [({"medical_device": True}, 4), ({"mobility": True}, 3), ({"lives_alone": True}, 3), ({"medical_device": False}, 1), ({}, 1)],
)
def test_stored_requester_flags_raise_the_floor(flags, floor):
    assert urgency_floor("Need some water", flags).floor == floor


def test_text_and_stored_flags_combine_and_take_the_max():
    result = urgency_floor("Need a ride, I use a wheelchair", {"lives_alone": True})
    assert result.floor == 4 and {F.mobility, F.lives_alone} <= result.flags


@pytest.mark.parametrize("text", ["My father can't breathe", "Mi padre no puede respirar", "Water is rising inside the house, baby here"])
def test_emergency_wins_over_high_terms(text):
    result = urgency_floor(text, {"mobility": True})
    assert result.floor == 5 and result.emergency
