"""Role 2: Symptom-first keyword guidance using per-symptom MedGemma calls."""

from __future__ import annotations

import asyncio
import json
import logging
from difflib import SequenceMatcher
from typing import TypeVar

from backend.config import settings
from backend.medgemma.client import chat_completion
from backend.medgemma.fixed_symptom_keywords import get_fixed_keywords_for_symptom
from backend.medgemma.json_utils import clean_json_response
from backend.medgemma.structured_extraction import isolate_symptoms
from backend.models import (
    EncounterStateData,
    KeywordSuggestionGroup,
    SymptomFocus,
    SymptomKeywordPipelineResult,
    SymptomKeywordState,
    SymptomKnownInfo,
)
from backend.prompts import (
    SYMPTOM_KEYWORDS_SYSTEM,
    SYMPTOM_KEYWORDS_USER,
    SYMPTOM_SUMMARY_SYSTEM,
    SYMPTOM_SUMMARY_USER,
)

logger = logging.getLogger(__name__)

PRIORITY_VALUES = {"critical", "high", "medium", "low"}
T = TypeVar("T")


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _dedup_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for keyword in keywords:
        cleaned = keyword.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _normalize_priority(value: object) -> str:
    text = str(value).strip().lower()
    return text if text in PRIORITY_VALUES else "medium"


def _parse_json_object(raw: str) -> dict:
    cleaned = clean_json_response(raw)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")
    return parsed


async def _chat_json_with_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    call_type: str,
) -> dict | None:
    raw = await chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        call_type=call_type,
    )
    try:
        return _parse_json_object(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        if not settings.medgemma_parse_retry_enabled:
            logger.error("%s parse failed (retry disabled): %s", call_type, exc)
            return None

        logger.warning("%s parse failed, retrying: %s", call_type, exc)
        raw = await chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt + "\n\nIMPORTANT: Output ONLY valid JSON, no other text.",
            max_tokens=max_tokens,
            call_type=call_type,
        )
        try:
            return _parse_json_object(raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.error("%s failed after retry", call_type)
            return None


def _merge_string_lists(existing: list[str], new: list[str]) -> list[str]:
    return _dedup_keywords(existing + new)


def _merge_known_info(existing: SymptomKnownInfo, delta: SymptomKnownInfo) -> SymptomKnownInfo:
    return SymptomKnownInfo(
        duration=delta.duration or existing.duration,
        onset=delta.onset or existing.onset,
        location=delta.location or existing.location,
        character=delta.character or existing.character,
        radiation=delta.radiation or existing.radiation,
        severity=delta.severity or existing.severity,
        time_course=delta.time_course or existing.time_course,
        associated=_merge_string_lists(existing.associated, delta.associated),
        aggravating=_merge_string_lists(existing.aggravating, delta.aggravating),
        relieving=_merge_string_lists(existing.relieving, delta.relieving),
        negatives=_merge_string_lists(existing.negatives, delta.negatives),
        red_flags=_merge_string_lists(existing.red_flags, delta.red_flags),
        notes=_merge_string_lists(existing.notes, delta.notes),
        last_updated_turn=max(existing.last_updated_turn, delta.last_updated_turn),
    )


def _merge_active_keywords(
    previous_active: list[str],
    addressed_keywords: list[str],
    new_keywords: list[str],
) -> list[str]:
    active: list[str] = []
    seen: set[str] = set()
    for keyword in previous_active:
        cleaned = keyword.strip()
        lowered = cleaned.lower()
        if not cleaned or _is_keyword_addressed(cleaned, addressed_keywords):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        active.append(cleaned)

    for keyword in new_keywords:
        cleaned = keyword.strip()
        lowered = cleaned.lower()
        if not cleaned or _is_keyword_addressed(cleaned, addressed_keywords) or lowered in seen:
            continue
        seen.add(lowered)
        active.append(cleaned)

    return active


def _is_keyword_addressed(keyword: str, addressed_keywords: list[str]) -> bool:
    cleaned = keyword.strip().lower()
    if not cleaned:
        return False

    for addressed in addressed_keywords:
        addressed_cleaned = addressed.strip().lower()
        if not addressed_cleaned:
            continue
        if cleaned == addressed_cleaned:
            return True
        if _similar(cleaned, addressed_cleaned) > settings.question_similarity_threshold:
            return True
    return False


def _merge_unresolved_keywords_with_fixed(
    *,
    fixed_keywords: list[str],
    model_new_keywords: list[str],
    addressed_keywords: list[str],
) -> list[str]:
    merged = _dedup_keywords(fixed_keywords + model_new_keywords)
    return [
        keyword
        for keyword in merged
        if not _is_keyword_addressed(keyword, addressed_keywords)
    ]


def _filter_baseline_duplicate_keywords(
    model_new_keywords: list[str],
    baseline_fixed_keywords: list[str],
) -> list[str]:
    return [
        keyword
        for keyword in model_new_keywords
        if not _is_keyword_addressed(keyword, baseline_fixed_keywords)
    ]


def _resolve_map_value(mapping: dict[str, T], symptom_name: str) -> T | None:
    if symptom_name in mapping:
        return mapping[symptom_name]

    for existing_key, value in mapping.items():
        if _similar(existing_key, symptom_name) > settings.question_similarity_threshold:
            return value
    return None


def _find_last_mention(text_lower: str, symptom: SymptomFocus) -> int:
    candidates = [symptom.canonical_name, *symptom.aliases]
    indices: list[int] = []
    for candidate in candidates:
        cleaned = candidate.strip().lower()
        if not cleaned:
            continue
        idx = text_lower.rfind(cleaned)
        if idx >= 0:
            indices.append(idx)
    return max(indices) if indices else -1


def _sort_symptoms_by_latest_mention(transcript: str, symptoms: list[SymptomFocus]) -> list[SymptomFocus]:
    transcript_lower = transcript.lower()
    indexed = []
    for idx, symptom in enumerate(symptoms):
        last_mention = _find_last_mention(transcript_lower, symptom)
        indexed.append((last_mention >= 0, last_mention, idx, symptom))

    indexed.sort(
        key=lambda item: (
            0 if item[0] else 1,
            -item[1] if item[0] else 0,
            item[2],
        )
    )

    sorted_symptoms: list[SymptomFocus] = []
    for order, (_, _, _, symptom) in enumerate(indexed, start=1):
        sorted_symptoms.append(
            SymptomFocus(
                canonical_name=symptom.canonical_name,
                aliases=symptom.aliases,
                priority=symptom.priority,
                first_seen_turn=symptom.first_seen_turn or order,
            )
        )
    return sorted_symptoms


async def _generate_symptom_summary_delta(
    symptom_name: str,
    transcript: str,
    current_known_info: SymptomKnownInfo,
) -> SymptomKnownInfo:
    prompt = SYMPTOM_SUMMARY_USER.format(
        symptom=symptom_name,
        transcript=transcript,
        current_known_info=current_known_info.model_dump_json(indent=2),
    )
    data = await _chat_json_with_retry(
        system_prompt=SYMPTOM_SUMMARY_SYSTEM,
        user_prompt=prompt,
        max_tokens=512,
        call_type="symptom_summary",
    )
    if data is None:
        return SymptomKnownInfo()

    payload = data.get("known_info_delta", {})
    if not isinstance(payload, dict):
        logger.warning("symptom_summary returned non-object known_info_delta for %s", symptom_name)
        return SymptomKnownInfo()

    try:
        return SymptomKnownInfo(**payload)
    except ValueError:
        logger.warning("symptom_summary payload validation failed for %s", symptom_name)
        return SymptomKnownInfo()


async def _generate_symptom_keyword_update(
    symptom_name: str,
    transcript: str,
    known_info: SymptomKnownInfo,
    previous_active_keywords: list[str],
    baseline_fixed_keywords: list[str],
) -> SymptomKeywordState:
    prompt = SYMPTOM_KEYWORDS_USER.format(
        symptom=symptom_name,
        transcript=transcript,
        known_info=known_info.model_dump_json(indent=2),
        previous_active_keywords=json.dumps(previous_active_keywords, indent=2),
        baseline_fixed_keywords=json.dumps(baseline_fixed_keywords, indent=2),
    )
    data = await _chat_json_with_retry(
        system_prompt=SYMPTOM_KEYWORDS_SYSTEM,
        user_prompt=prompt,
        max_tokens=512,
        call_type="symptom_keywords",
    )

    if data is None:
        return SymptomKeywordState(
            symptom=symptom_name,
            addressed_keywords=[],
            new_keywords=[],
            active_keywords=previous_active_keywords,
            priority="medium",
        )

    addressed_raw = data.get("addressed_keywords", [])
    new_raw = data.get("new_keywords", [])

    addressed_keywords = _dedup_keywords([str(k) for k in addressed_raw]) if isinstance(addressed_raw, list) else []
    new_keywords = _dedup_keywords([str(k) for k in new_raw]) if isinstance(new_raw, list) else []
    new_keywords = _filter_baseline_duplicate_keywords(new_keywords, baseline_fixed_keywords)

    return SymptomKeywordState(
        symptom=symptom_name,
        addressed_keywords=addressed_keywords,
        new_keywords=new_keywords,
        active_keywords=[],
        rationale=(str(data.get("rationale")).strip() if data.get("rationale") is not None else None),
        priority=_normalize_priority(data.get("priority", "medium")),
    )


async def _process_symptom(
    symptom: SymptomFocus,
    transcript: str,
    encounter_state: EncounterStateData,
) -> tuple[str, SymptomKnownInfo, SymptomKeywordState, KeywordSuggestionGroup | None]:
    symptom_name = symptom.canonical_name
    current_known_info = _resolve_map_value(encounter_state.symptom_known_info, symptom_name) or SymptomKnownInfo()
    current_keyword_state = _resolve_map_value(encounter_state.symptom_keyword_state, symptom_name)
    previous_active = current_keyword_state.active_keywords if current_keyword_state else []

    summary_delta = await _generate_symptom_summary_delta(
        symptom_name=symptom_name,
        transcript=transcript,
        current_known_info=current_known_info,
    )
    merged_known_info = _merge_known_info(current_known_info, summary_delta)
    fixed_keywords = get_fixed_keywords_for_symptom(symptom_name)

    keyword_update = await _generate_symptom_keyword_update(
        symptom_name=symptom_name,
        transcript=transcript,
        known_info=merged_known_info,
        previous_active_keywords=previous_active,
        baseline_fixed_keywords=fixed_keywords,
    )
    unresolved_keywords = _merge_unresolved_keywords_with_fixed(
        fixed_keywords=fixed_keywords,
        model_new_keywords=keyword_update.new_keywords,
        addressed_keywords=keyword_update.addressed_keywords,
    )

    active_keywords = _merge_active_keywords(
        previous_active=previous_active,
        addressed_keywords=keyword_update.addressed_keywords,
        new_keywords=unresolved_keywords,
    )

    updated_keyword_state = SymptomKeywordState(
        symptom=symptom_name,
        addressed_keywords=keyword_update.addressed_keywords,
        new_keywords=keyword_update.new_keywords,
        active_keywords=active_keywords,
        rationale=keyword_update.rationale,
        priority=keyword_update.priority,
    )

    group: KeywordSuggestionGroup | None = None
    if active_keywords or updated_keyword_state.priority == "critical":
        group = KeywordSuggestionGroup(
            category=symptom_name,
            priority=updated_keyword_state.priority,
            keywords=active_keywords,
            rationale=updated_keyword_state.rationale,
        )

    return symptom_name, merged_known_info, updated_keyword_state, group


def _fallback_general_group() -> KeywordSuggestionGroup:
    return KeywordSuggestionGroup(
        category="General Clarification",
        priority="high",
        keywords=["chief complaint", "timeline", "red flags"],
        rationale="No distinct symptom isolated yet; clarify presenting problem and safety red flags.",
    )


async def generate_keyword_suggestions_with_state(
    encounter_state: EncounterStateData,
    transcript: str | None = None,
) -> SymptomKeywordPipelineResult:
    """Generate per-symptom keyword groups and updated per-symptom state."""
    if not settings.enable_symptom_pipeline:
        return SymptomKeywordPipelineResult(
            groups=[_fallback_general_group()],
            isolated_symptoms=encounter_state.isolated_symptoms,
            symptom_known_info=encounter_state.symptom_known_info,
            symptom_keyword_state=encounter_state.symptom_keyword_state,
        )

    transcript_text = (transcript or "").strip()
    isolated = await isolate_symptoms(
        transcript=transcript_text,
        previous_symptoms=encounter_state.isolated_symptoms,
    )

    if not isolated:
        return SymptomKeywordPipelineResult(
            groups=[_fallback_general_group()],
            isolated_symptoms=[],
            symptom_known_info=encounter_state.symptom_known_info,
            symptom_keyword_state=encounter_state.symptom_keyword_state,
        )

    ordered_symptoms = _sort_symptoms_by_latest_mention(transcript_text, isolated)
    if settings.max_symptom_calls_per_cycle and settings.max_symptom_calls_per_cycle > 0:
        ordered_symptoms = ordered_symptoms[: settings.max_symptom_calls_per_cycle]

    tasks = [
        asyncio.create_task(
            _process_symptom(symptom=symptom, transcript=transcript_text, encounter_state=encounter_state)
        )
        for symptom in ordered_symptoms
    ]

    grouped_results: dict[str, tuple[SymptomKnownInfo, SymptomKeywordState, KeywordSuggestionGroup | None]] = {}
    for done in asyncio.as_completed(tasks):
        try:
            symptom_name, known_info, keyword_state, group = await done
        except Exception as exc:
            logger.error("Per-symptom keyword processing failed: %s", exc, exc_info=exc)
            continue
        grouped_results[symptom_name] = (known_info, keyword_state, group)

    symptom_known_info: dict[str, SymptomKnownInfo] = {}
    symptom_keyword_state: dict[str, SymptomKeywordState] = {}
    groups: list[KeywordSuggestionGroup] = []

    for symptom in ordered_symptoms:
        symptom_name = symptom.canonical_name
        payload = grouped_results.get(symptom_name)
        if payload is None:
            continue
        known_info, keyword_state, group = payload
        symptom_known_info[symptom_name] = known_info
        symptom_keyword_state[symptom_name] = keyword_state
        if group is not None:
            groups.append(group)

    if not groups:
        groups = [_fallback_general_group()]

    return SymptomKeywordPipelineResult(
        groups=groups,
        isolated_symptoms=ordered_symptoms,
        symptom_known_info=symptom_known_info,
        symptom_keyword_state=symptom_keyword_state,
    )


async def generate_keyword_suggestions(
    encounter_state: EncounterStateData,
    transcript: str | None = None,
) -> list[KeywordSuggestionGroup]:
    """Backward-compatible wrapper returning only keyword groups."""
    result = await generate_keyword_suggestions_with_state(
        encounter_state=encounter_state,
        transcript=transcript,
    )
    return result.groups
