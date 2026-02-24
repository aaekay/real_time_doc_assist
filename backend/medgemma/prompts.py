"""Deprecated: prompt templates have moved to backend.prompts.

This shim re-exports all constants for backward compatibility.
Import from backend.prompts instead.
"""

from backend.prompts import (  # noqa: F401
    CHIEF_COMPLAINT_SYSTEM,
    CHIEF_COMPLAINT_USER,
    DEMOGRAPHICS_SYSTEM,
    DEMOGRAPHICS_USER,
    QUESTION_SYSTEM,
    QUESTION_TRANSCRIPT_USER,
    QUESTION_USER,
    SUMMARY_SYSTEM,
    SUMMARY_USER,
)
