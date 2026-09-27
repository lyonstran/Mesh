"""Enums and request/response bodies for the MVP (PLAN.md §0.1). Mirror in frontend/src/lib/types.ts."""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Role(StrEnum):
    requester = "requester"
    helper = "helper"  # shown as "Volunteer" in the UI


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


class HelperProfile(BaseModel):
    skills: list[Skill] = []
    custom_skills: list[str] = []  # volunteer-entered skills not in the Skill enum
    resources: list[Resource] = []
    about: str = Field("", max_length=1000)  # "What I can offer"

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
    helper: HelperProfile | None = None
    requester_flags: RequesterFlags | None = None


class ProfileUpdate(BaseModel):
    role: Role | None = None
    name: str | None = Field(None, min_length=1, max_length=80)
    language: str | None = Field(None, min_length=2, max_length=10)
    background: str | None = Field(None, max_length=1000)
    helper: HelperProfile | None = None
    requester_flags: RequesterFlags | None = None


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class RequestCreate(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
