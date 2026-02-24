from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# --- WebSocket message types ---

class WSMessageType(str, Enum):
    TRANSCRIPT = "transcript"
    KEYWORD_SUGGESTIONS = "keyword_suggestions"
    ENCOUNTER_STATE = "encounter_state"
    SOAP_NOTE = "soap_note"
    SESSION_RESET = "session_reset"
    STATUS = "status"
    ERROR = "error"


class WSMessage(BaseModel):
    type: WSMessageType
    data: dict


# --- Encounter state ---

class Symptom(BaseModel):
    name: str
    duration: str | None = None
    severity: str | None = None
    character: str | None = None
    location: str | None = None
    onset: str | None = None          # SOCRATES: O
    radiation: str | None = None      # SOCRATES: R
    time_course: str | None = None    # SOCRATES: T
    aggravating: list[str] = Field(default_factory=list)
    relieving: list[str] = Field(default_factory=list)
    associated: list[str] = Field(default_factory=list)


class SymptomFocus(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    first_seen_turn: int = 0
    priority: str | None = None


class SymptomKnownInfo(BaseModel):
    duration: str | None = None
    onset: str | None = None
    location: str | None = None
    character: str | None = None
    radiation: str | None = None
    severity: str | None = None
    time_course: str | None = None
    associated: list[str] = Field(default_factory=list)
    aggravating: list[str] = Field(default_factory=list)
    relieving: list[str] = Field(default_factory=list)
    negatives: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    last_updated_turn: int = 0


class SymptomKeywordState(BaseModel):
    symptom: str
    addressed_keywords: list[str] = Field(default_factory=list)
    new_keywords: list[str] = Field(default_factory=list)
    active_keywords: list[str] = Field(default_factory=list)
    rationale: str | None = None
    priority: str = Field(default="medium")


class Medication(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None


class VitalSign(BaseModel):
    name: str
    value: str


class DemographicsData(BaseModel):
    name: str | None = None
    age: str | None = None
    sex: str | None = None
    other: list[str] = Field(default_factory=list)


class ChiefComplaintStructured(BaseModel):
    primary: str | None = None
    duration: str | None = None
    onset: str | None = None
    site: str | None = None
    character: str | None = None
    radiation: str | None = None
    severity: str | None = None
    time_course: str | None = None
    characteristics: list[str] = Field(default_factory=list)
    associated: list[str] = Field(default_factory=list)
    aggravating: list[str] = Field(default_factory=list)
    relieving: list[str] = Field(default_factory=list)


class EncounterStateData(BaseModel):
    demographics: DemographicsData = Field(default_factory=DemographicsData)
    chief_complaint: str | None = None
    chief_complaint_structured: ChiefComplaintStructured = Field(
        default_factory=ChiefComplaintStructured
    )
    symptoms: list[Symptom] = Field(default_factory=list)
    history_of_present_illness: str | None = None
    past_medical_history: list[str] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    family_history: list[str] = Field(default_factory=list)
    social_history: list[str] = Field(default_factory=list)
    review_of_systems: dict[str, list[str]] = Field(default_factory=dict)
    vitals: list[VitalSign] = Field(default_factory=list)
    physical_exam_findings: list[str] = Field(default_factory=list)
    domains_covered: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    isolated_symptoms: list[SymptomFocus] = Field(default_factory=list)
    symptom_known_info: dict[str, SymptomKnownInfo] = Field(default_factory=dict)
    symptom_keyword_state: dict[str, SymptomKeywordState] = Field(default_factory=dict)


# --- Suggested questions ---

class QuestionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class KeywordSuggestionGroup(BaseModel):
    category: str
    priority: QuestionPriority
    keywords: list[str] = Field(default_factory=list)
    rationale: str | None = None


class SymptomKeywordPipelineResult(BaseModel):
    groups: list[KeywordSuggestionGroup] = Field(default_factory=list)
    isolated_symptoms: list[SymptomFocus] = Field(default_factory=list)
    symptom_known_info: dict[str, SymptomKnownInfo] = Field(default_factory=dict)
    symptom_keyword_state: dict[str, SymptomKeywordState] = Field(default_factory=dict)


# --- SOAP note ---

class SOAPNote(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
