"""Role 1 extractors: focused and legacy structured extraction with MedGemma."""

import json
import logging

from backend.config import settings
from backend.models import (
    ChiefComplaintStructured,
    DemographicsData,
    EncounterStateData,
    SymptomFocus,
)
from backend.medgemma.client import chat_completion
from backend.medgemma.json_utils import clean_json_response
from backend.prompts import (
    CHIEF_COMPLAINT_SYSTEM,
    CHIEF_COMPLAINT_USER,
    DEMOGRAPHICS_SYSTEM,
    DEMOGRAPHICS_USER,
    SYMPTOM_ISOLATION_SYSTEM,
    SYMPTOM_ISOLATION_USER,
)

logger = logging.getLogger(__name__)


def _parse_json_payload(raw: str) -> dict:
    cleaned = clean_json_response(raw)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Extraction response must be a JSON object.")
    return data


async def extract_demographics(
    transcript: str,
    previous_state: EncounterStateData | None = None,
) -> DemographicsData:
    """Extract only demographics from transcript."""
    previous = (
        previous_state.demographics.model_copy(deep=True)
        if previous_state
        else DemographicsData()
    )
    prompt = DEMOGRAPHICS_USER.format(
        transcript=transcript,
        previous_demographics=previous.model_dump_json(indent=2),
    )

    raw = await chat_completion(
        system_prompt=DEMOGRAPHICS_SYSTEM,
        user_prompt=prompt,
        max_tokens=384,
        call_type="demographics_extraction",
    )

    try:
        data = _parse_json_payload(raw)
        payload = data.get("demographics", {})
        if payload is None:
            payload = {}
        return DemographicsData(**payload)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse demographics response, retrying: %s", e)
        raw = await chat_completion(
            system_prompt=DEMOGRAPHICS_SYSTEM,
            user_prompt=prompt + "\n\nIMPORTANT: Output ONLY valid JSON, no other text.",
            max_tokens=384,
            call_type="demographics_extraction",
        )
        try:
            data = _parse_json_payload(raw)
            payload = data.get("demographics", {})
            if payload is None:
                payload = {}
            return DemographicsData(**payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.error("Demographics extraction failed after retry. Returning previous values.")
            return previous


async def extract_chief_complaint(
    transcript: str,
    previous_state: EncounterStateData | None = None,
) -> tuple[str | None, ChiefComplaintStructured]:
    """Extract only chief complaint fields from transcript."""
    previous_chief = previous_state.chief_complaint if previous_state else None
    previous_structured = (
        previous_state.chief_complaint_structured.model_copy(deep=True)
        if previous_state
        else ChiefComplaintStructured()
    )
    previous_payload = json.dumps(
        {
            "chief_complaint": previous_chief,
            "chief_complaint_structured": previous_structured.model_dump(),
        },
        indent=2,
    )
    prompt = CHIEF_COMPLAINT_USER.format(
        transcript=transcript,
        previous_chief_complaint=previous_payload,
    )

    raw = await chat_completion(
        system_prompt=CHIEF_COMPLAINT_SYSTEM,
        user_prompt=prompt,
        max_tokens=512,
        call_type="chief_complaint_extraction",
    )

    try:
        data = _parse_json_payload(raw)
        chief = data.get("chief_complaint")
        chief_text = str(chief).strip() if chief is not None else None
        chief_text = chief_text or None

        structured_payload = data.get("chief_complaint_structured", {})
        if structured_payload is None:
            structured_payload = {}
        structured = ChiefComplaintStructured(**structured_payload)
        if chief_text is None and structured.primary:
            chief_text = structured.primary
        return chief_text, structured
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse chief complaint response, retrying: %s", e)
        raw = await chat_completion(
            system_prompt=CHIEF_COMPLAINT_SYSTEM,
            user_prompt=prompt + "\n\nIMPORTANT: Output ONLY valid JSON, no other text.",
            max_tokens=512,
            call_type="chief_complaint_extraction",
        )
        try:
            data = _parse_json_payload(raw)
            chief = data.get("chief_complaint")
            chief_text = str(chief).strip() if chief is not None else None
            chief_text = chief_text or None

            structured_payload = data.get("chief_complaint_structured", {})
            if structured_payload is None:
                structured_payload = {}
            structured = ChiefComplaintStructured(**structured_payload)
            if chief_text is None and structured.primary:
                chief_text = structured.primary
            return chief_text, structured
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.error("Chief complaint extraction failed after retry. Returning previous values.")
            return previous_chief, previous_structured


def _dedup_symptom_focuses(symptoms: list[SymptomFocus]) -> list[SymptomFocus]:
    seen: dict[str, SymptomFocus] = {}
    for symptom in symptoms:
        key = symptom.canonical_name.strip().lower()
        if not key:
            continue
        if key not in seen:
            seen[key] = SymptomFocus(
                canonical_name=symptom.canonical_name.strip(),
                aliases=[a.strip() for a in symptom.aliases if a and a.strip()],
                priority=symptom.priority,
                first_seen_turn=symptom.first_seen_turn,
            )
            continue

        existing = seen[key]
        alias_seen = {a.lower() for a in existing.aliases}
        merged_aliases = list(existing.aliases)
        for alias in symptom.aliases:
            cleaned = alias.strip()
            if cleaned and cleaned.lower() not in alias_seen:
                alias_seen.add(cleaned.lower())
                merged_aliases.append(cleaned)
        seen[key] = SymptomFocus(
            canonical_name=existing.canonical_name,
            aliases=merged_aliases,
            priority=symptom.priority or existing.priority,
            first_seen_turn=min(
                [value for value in [existing.first_seen_turn, symptom.first_seen_turn] if value >= 0]
                or [0]
            ),
        )
    return list(seen.values())


async def isolate_symptoms(
    transcript: str,
    previous_symptoms: list[SymptomFocus] | None = None,
) -> list[SymptomFocus]:
    """Isolate distinct symptoms from transcript for symptom-first questioning."""
    previous = previous_symptoms or []
    prompt = SYMPTOM_ISOLATION_USER.format(
        transcript=transcript,
        previous_symptoms=json.dumps(
            [s.model_dump() for s in previous],
            indent=2,
        ),
    )

    raw = await chat_completion(
        system_prompt=SYMPTOM_ISOLATION_SYSTEM,
        user_prompt=prompt,
        max_tokens=512,
        call_type="symptom_isolation",
    )

    def _parse(raw_payload: str) -> list[SymptomFocus]:
        data = _parse_json_payload(raw_payload)
        payload = data.get("symptoms", [])
        if not isinstance(payload, list):
            raise ValueError("symptoms must be a list")
        parsed: list[SymptomFocus] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("canonical_name", "")).strip()
            if not name:
                continue
            aliases_raw = item.get("aliases", [])
            aliases = (
                [str(alias).strip() for alias in aliases_raw if str(alias).strip()]
                if isinstance(aliases_raw, list)
                else []
            )
            parsed.append(
                SymptomFocus(
                    canonical_name=name,
                    aliases=aliases,
                    priority=(
                        str(item.get("priority")).strip().lower()
                        if item.get("priority") is not None
                        else None
                    ),
                    first_seen_turn=0,
                )
            )
        return _dedup_symptom_focuses(parsed)

    try:
        return _parse(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        if not settings.medgemma_parse_retry_enabled:
            logger.error("Symptom isolation parse failed (retry disabled): %s", e)
            return previous

        logger.warning("Failed to parse symptom isolation response, retrying: %s", e)
        raw = await chat_completion(
            system_prompt=SYMPTOM_ISOLATION_SYSTEM,
            user_prompt=prompt + "\n\nIMPORTANT: Output ONLY valid JSON, no other text.",
            max_tokens=512,
            call_type="symptom_isolation",
        )
        try:
            return _parse(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.error("Symptom isolation failed after retry. Returning previous values.")
            return previous
