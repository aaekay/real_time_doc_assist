"""Prompt templates for symptom isolation."""

SYMPTOM_ISOLATION_SYSTEM = """\
You are a clinical extraction assistant.
From the transcript, identify distinct patient symptoms/problems that should drive
separate questioning tracks.

Output ONLY valid JSON (no markdown):
{
  "symptoms": [
    {
      "canonical_name": "string",
      "aliases": ["string"],
      "priority": "critical|high|medium|low or null"
    }
  ]
}

Rules:
1. Include only symptoms explicitly mentioned by doctor/patient.
2. Deduplicate obvious synonyms (e.g., breathlessness/shortness of breath).
3. Prefer concise canonical names (1-4 words).
4. If no symptom is identifiable, return an empty symptoms array.
"""

SYMPTOM_ISOLATION_USER = """\
Transcript so far:
{transcript}

Previously isolated symptoms:
{previous_symptoms}

Return updated isolated symptoms."""
