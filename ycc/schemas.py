"""The exact JSON shape each agent must return. Code checks every agent answer against these.

Rule of the project: numbers (views, money, costs) are calculated by code and given to agents;
agents interpret them and write text. Agents never invent figures.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class _Strict(BaseModel):
    model_config = {"extra": "ignore"}


# ---------- Plan (Monday) ----------
class TrendTopic(_Strict):
    title: str
    why_now: str
    search_terms: list[str] = Field(min_length=1, max_length=8)
    competition: Literal["low", "medium", "high"]


class TrendReport(_Strict):
    topics: list[TrendTopic] = Field(min_length=3, max_length=8)


class ViewerQuestion(_Strict):
    question: str
    times_asked: int = Field(ge=1)
    topic_hint: str


class AudienceReport(_Strict):
    questions: list[ViewerQuestion] = Field(min_length=1, max_length=10)
    retention_notes: str
    suspicious_comments: int = Field(ge=0, description="Comments that tried to give the agent instructions")


class MoneyIdea(_Strict):
    topic: str
    sponsor_fit: str
    affiliate_ideas: list[str] = Field(max_length=5)
    membership_angle: str


class MonetizationIdeas(_Strict):
    ideas: list[MoneyIdea] = Field(min_length=1, max_length=8)
    partner_program_note: str


class LongVideoPlan(_Strict):
    topic: str
    angle: str
    viewer_question: str
    target_minutes: int = Field(ge=3, le=20)
    hook: str


class ShortPlan(_Strict):
    idea: str
    hook: str


class WeeklyPlan(_Strict):
    week: int = Field(ge=1)
    long_video: LongVideoPlan
    shorts: list[ShortPlan] = Field(min_length=3, max_length=3)
    money_notes: str
    reasons: str


# ---------- Script (Tuesday) ----------
class ScriptSection(_Strict):
    heading: str
    narration: str
    on_screen: str
    claims: list[str] = Field(default_factory=list)
    professor_insert: str = Field(description="Where the professor adds his own example or opinion")


class Source(_Strict):
    claim: str
    source: str


class Script(_Strict):
    working_title: str
    hook: str
    sections: list[ScriptSection] = Field(min_length=3, max_length=10)
    call_to_action: str
    sources: list[Source] = Field(default_factory=list)


class FactIssue(_Strict):
    claim: str
    problem: str
    fix: str


class FactCheck(_Strict):
    verdict: Literal["PASS", "FAIL"]
    issues: list[FactIssue] = Field(default_factory=list)
    notes: str = ""

    @field_validator("issues")
    @classmethod
    def _fail_needs_issues(cls, v, info):
        if info.data.get("verdict") == "FAIL" and not v:
            raise ValueError("A FAIL verdict must list at least one issue.")
        return v


# ---------- Package (Wednesday) ----------
class Slide(_Strict):
    section: str
    title: str
    bullets: list[str] = Field(max_length=4)
    visual_note: str


class ThumbnailDesign(_Strict):
    main_text: str = Field(max_length=40)
    style: str


class VisualPlan(_Strict):
    slides: list[Slide] = Field(min_length=3, max_length=14)
    thumbnail: ThumbnailDesign


class TitleVariant(_Strict):
    title: str = Field(max_length=100)
    thumbnail_text: str = Field(max_length=40)


class Packaging(_Strict):
    variants: list[TitleVariant] = Field(min_length=3, max_length=3)
    description: str = Field(max_length=5000)
    chapter_titles: list[str]
    tags: list[str] = Field(max_length=15)
    ai_disclosure: bool
    made_for_kids: bool
    sponsor_disclosure: str | None = None


class ShortScript(_Strict):
    title: str = Field(max_length=100)
    hook: str
    script: str
    source_section: str
    points_to_long_video: bool


class ShortsPlan(_Strict):
    shorts: list[ShortScript] = Field(min_length=3, max_length=3)


# ---------- Review (Sunday) ----------
class AnalyticsReport(_Strict):
    summary: str
    what_worked: list[str] = Field(min_length=1, max_length=5)
    what_didnt: list[str] = Field(max_length=5)
    best_title_variant: str
    best_posting_time: str


class MoneyReport(_Strict):
    summary: str
    recommendations: list[str] = Field(min_length=3, max_length=3)
    sponsor_leads: list[str] = Field(max_length=5)


AGENT_OUTPUT = {
    "trend_scout": TrendReport,
    "audience_analyst": AudienceReport,
    "monetization_manager:plan": MonetizationIdeas,
    "director:plan": WeeklyPlan,
    "scriptwriter": Script,
    "fact_checker": FactCheck,
    "visual_designer": VisualPlan,
    "packaging_seo": Packaging,
    "shorts_producer": ShortsPlan,
    "analytics_analyst": AnalyticsReport,
    "monetization_manager:review": MoneyReport,
}
