"""Enums and request/response bodies for the MVP (PLAN.md §0.1). Mirror in frontend/src/lib/types.ts."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Role(StrEnum):
    requester = "requester"
    helper = "helper"  # shown as "Volunteer" in the UI


def held_roles(user: dict) -> list[Role]:
    """Profiles the user holds. Falls back to `role` for accounts created before `roles` existed."""
    roles = user.get("roles") or ([user["role"]] if user.get("role") else [])
    return [Role(r) for r in roles]


class RequestStatus(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


ACTIVE_STATUSES = (RequestStatus.OPEN, RequestStatus.CLAIMED)


class Skill(StrEnum):
    first_aid = "first_aid"
    cpr = "cpr"
    nursing = "nursing"
    chainsaw = "chainsaw"
    heavy_lifting = "heavy_lifting"
    driving = "driving"
    spanish = "spanish"
    other_language = "other_language"
    electrical_safe = "electrical_safe"
    childcare = "childcare"
    elder_care = "elder_care"


class Resource(StrEnum):
    vehicle = "vehicle"
    truck = "truck"
    generator = "generator"
    power_bank = "power_bank"
    water = "water"
    food = "food"
    tarp = "tarp"
    sandbags = "sandbags"
    ac_space = "ac_space"
    n95_masks = "n95_masks"
    medical_kit = "medical_kit"


MAX_CUSTOM_SKILLS = 10
MAX_CUSTOM_SKILL_LENGTH = 40


MAX_RADIUS_KM = 15
DEFAULT_RADIUS_KM = 10


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class HelperProfile(BaseModel):
    skills: list[Skill] = []
    custom_skills: list[str] = []  # volunteer-entered skills not in the Skill enum
    resources: list[Resource] = []
    about: str = Field("", max_length=1000)  # "What I can offer"
    radius_km: float = Field(DEFAULT_RADIUS_KM, ge=1, le=MAX_RADIUS_KM)  # how far from home_location they will travel
    show_area_to_requesters: bool = True  # appear as a fuzzed area on nearby requesters' maps (opt-out)

    @field_validator("custom_skills")
    @classmethod
    def _clean_custom_skills(cls, value: list[str]) -> list[str]:
        """Trim, collapse whitespace, drop blanks and case-insensitive duplicates, enforce limits."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            skill = " ".join(raw.split())
            if not skill or skill.casefold() in seen:
                continue
            if len(skill) > MAX_CUSTOM_SKILL_LENGTH:
                raise ValueError(f"Custom skills can be at most {MAX_CUSTOM_SKILL_LENGTH} characters")
            seen.add(skill.casefold())
            cleaned.append(skill)
        if len(cleaned) > MAX_CUSTOM_SKILLS:
            raise ValueError(f"You can add at most {MAX_CUSTOM_SKILLS} custom skills")
        return cleaned


class RequesterFlags(BaseModel):
    medical_device: bool = False
    mobility: bool = False
    lives_alone: bool = False


class GoogleCredential(BaseModel):
    credential: str


class DemoLogin(BaseModel):
    user_id: str


class OnboardingIn(BaseModel):
    role: Role
    name: str = Field(min_length=1, max_length=80)
    language: str = Field("en", min_length=2, max_length=10)
    background: str = Field("", max_length=1000)
    home_location: GeoPoint | None = None
    helper: HelperProfile | None = None
    requester_flags: RequesterFlags | None = None


class ProfileUpdate(BaseModel):
    role: Role | None = None
    name: str | None = Field(None, min_length=1, max_length=80)
    language: str | None = Field(None, min_length=2, max_length=10)
    background: str | None = Field(None, max_length=1000)
    home_location: GeoPoint | None = None  # send null to clear
    helper: HelperProfile | None = None
    requester_flags: RequesterFlags | None = None


class AddRoleIn(BaseModel):
    role: Role
    helper: HelperProfile | None = None
    requester_flags: RequesterFlags | None = None


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class Category(StrEnum):
    """Request categories (PLAN.md §9.1)."""

    power = "power"
    water = "water"
    food = "food"
    medical_supplies = "medical_supplies"
    transport = "transport"
    shelter = "shelter"
    cooling = "cooling"
    warming = "warming"
    debris = "debris"
    respiratory = "respiratory"
    welfare_check = "welfare_check"
    supplies = "supplies"
    other = "other"


class TriageFlag(StrEnum):
    """Vulnerability flags on a request (PLAN.md §9.1)."""

    medical_device = "medical_device"
    mobility = "mobility"
    elderly = "elderly"
    lives_alone = "lives_alone"
    infant = "infant"
    language_barrier = "language_barrier"


class Triage(BaseModel):
    """The triage card: rules merged with the LLM (PLAN.md §9.2). Urgency is never below the rule floor."""

    category: Category
    urgency: int = Field(ge=1, le=5)
    urgency_rule_floor: int = Field(ge=1, le=5)
    emergency: bool
    flags: list[TriageFlag]
    needs: list[str]
    summary: str
    language: str
    source: Literal["ai", "rules"]  # "rules" when the LLM was skipped or failed


class RequestCreate(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    location: GeoPoint | None = None  # optional so the API degrades gracefully; the app asks for it
    category_override: Category | None = None  # the requester's pick on the preview card; never changes urgency


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


HazardType = Literal["tornado", "severe_storm", "flood", "heat", "air_quality", "winter", "tropical", "wind", "other"]


class Hazard(BaseModel):
    """One hazard in a hazard report (PLAN.md §7). NWS alerts are official; Open-Meteo signals are derived (level <= 2)."""

    type: HazardType
    level: int = Field(ge=1, le=3)
    source: Literal["NWS", "Open-Meteo"]
    official: bool
    event: str | None = None  # NWS event name, e.g. "Severe Thunderstorm Warning"
    headline: str | None = None
    expires: str | None = None  # ISO
    instruction: str | None = None
    value: float | None = None  # derived signals: the reading that crossed the threshold
    unit: str | None = None
    category: str | None = None  # e.g. EPA AQI category


class HazardReport(BaseModel):
    """GET /api/hazards (PLAN.md §7). Levels come from code (tables + thresholds), never from the LLM."""

    level: int = Field(ge=0, le=3)  # max over hazards, 0 when there are none
    hazards: list[Hazard]
    likely_needs: list[str]
    current: dict[str, float | None]
    simulated: bool
    sources_failed: list[Literal["NWS", "Open-Meteo forecast", "Open-Meteo air quality"]]
    fetched_at: str  # ISO
