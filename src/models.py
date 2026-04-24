from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Opportunity(BaseModel):
    id: str
    title: str
    type: Literal["internship", "hackathon", "program", "course"]
    topic_tags: list[str] = []
    level: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    location: str | None = None
    remote: bool = False
    deadline: str | None = None
    duration: str | None = None
    skills: list[str] = []
    description: str | None = None
    source_name: str
    source_url: str | None = None
    collected_at: str
    is_live_api: bool = False

    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    relevance_score: float
    type_score: float
    level_score: float
    remote_score: float
    deadline_score: float
    penalties: float


class ScoredOpportunity(BaseModel):
    opportunity: Opportunity
    score: float
    score_100: float = 0.0
    reason: str
    breakdown: ScoreBreakdown | None = None


class QueryIntent(BaseModel):
    original: str
    keywords: list[str]
    is_beginner: bool = False
    user_level: Literal["beginner", "intermediate", "advanced"] | None = None
    type_preferences: list[str] | None = None
    topics: list[str] | None = None
    wants_remote: bool = False
    is_urgent: bool = False
    live_query: str = "машинное обучение"
    use_live_api: bool = True


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    offline: bool = False
    save_json: bool = False


class AgentResponse(BaseModel):
    answer: str
    opportunities: list[ScoredOpportunity]
    tools_used: list[str]
    caveats: list[str]
    query: str


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    llm_provider: str
    llm_note: str


class SourceInfo(BaseModel):
    name: str
    type: str
    url: str | None
    notes: str
    collected_at: str
