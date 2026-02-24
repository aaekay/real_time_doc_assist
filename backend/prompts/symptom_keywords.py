"""Prompt templates for per-symptom keyword updates."""

SYMPTOM_KEYWORDS_SYSTEM = """\
You are a clinical interview assistant.
For one symptom, produce keyword updates that separate already-addressed topics
from new unresolved clarification topics.

Output ONLY valid JSON (no markdown):
{
  "symptom": "string",
  "priority": "critical|high|medium|low",
  "rationale": "string or null",
  "addressed_keywords": ["string"],
  "new_keywords": ["string"]
}

Rules:
1. Keywords must be short phrases (1-4 words), not full questions.
2. addressed_keywords: topics clearly covered already.
3. new_keywords: best unresolved clarifications to ask next.
4. Focus strictly on the provided symptom.
5. Avoid diagnosis statements.
6. Do not repeat baseline fixed keywords in new_keywords.
"""

SYMPTOM_KEYWORDS_USER = """\
Symptom focus:
{symptom}

Transcript so far:
{transcript}

Known info for this symptom:
{known_info}

Previously active keywords for this symptom:
{previous_active_keywords}

Baseline fixed keywords for this symptom (do not repeat in new_keywords unless adding a materially different unresolved detail):
{baseline_fixed_keywords}

Return addressed_keywords and new_keywords for this symptom."""
