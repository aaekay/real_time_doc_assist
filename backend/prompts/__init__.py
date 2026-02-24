"""Centralized prompt templates for all MedGemma roles.

Import any prompt constant directly:
    from backend.prompts import QUESTION_SYSTEM, DEMOGRAPHICS_USER
"""

from backend.prompts.demographics import DEMOGRAPHICS_SYSTEM, DEMOGRAPHICS_USER
from backend.prompts.chief_complaint import CHIEF_COMPLAINT_SYSTEM, CHIEF_COMPLAINT_USER
from backend.prompts.question_keywords import (
    QUESTION_SYSTEM,
    QUESTION_USER,
    QUESTION_TRANSCRIPT_USER,
)
from backend.prompts.symptom_isolation import (
    SYMPTOM_ISOLATION_SYSTEM,
    SYMPTOM_ISOLATION_USER,
)
from backend.prompts.symptom_summary import (
    SYMPTOM_SUMMARY_SYSTEM,
    SYMPTOM_SUMMARY_USER,
)
from backend.prompts.symptom_keywords import (
    SYMPTOM_KEYWORDS_SYSTEM,
    SYMPTOM_KEYWORDS_USER,
)
from backend.prompts.summary import SUMMARY_SYSTEM, SUMMARY_USER

__all__ = [
    "DEMOGRAPHICS_SYSTEM",
    "DEMOGRAPHICS_USER",
    "CHIEF_COMPLAINT_SYSTEM",
    "CHIEF_COMPLAINT_USER",
    "QUESTION_SYSTEM",
    "QUESTION_USER",
    "QUESTION_TRANSCRIPT_USER",
    "SYMPTOM_ISOLATION_SYSTEM",
    "SYMPTOM_ISOLATION_USER",
    "SYMPTOM_SUMMARY_SYSTEM",
    "SYMPTOM_SUMMARY_USER",
    "SYMPTOM_KEYWORDS_SYSTEM",
    "SYMPTOM_KEYWORDS_USER",
    "SUMMARY_SYSTEM",
    "SUMMARY_USER",
]
