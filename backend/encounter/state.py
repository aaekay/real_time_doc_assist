"""EncounterState: accumulative merge of extracted clinical data with deduplication."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from backend.models import (
    EncounterStateData,
    Symptom,
    SymptomFocus,
    SymptomKnownInfo,
    SymptomKeywordState,
    Medication,
    VitalSign,
    DemographicsData,
    ChiefComplaintStructured,
)
from backend.config import settings

logger = logging.getLogger(__name__)


def _similar(a: str, b: str) -> float:
    """Fuzzy string similarity ratio."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _dedup_strings(existing: list[str], new: list[str]) -> list[str]:
    """Merge new strings into existing list, skipping near-duplicates."""
    result = list(existing)
    for item in new:
        if not any(_similar(item, e) > settings.question_similarity_threshold for e in result):
            result.append(item)
    return result


def _dedup_symptoms(existing: list[Symptom], new: list[Symptom]) -> list[Symptom]:
    """Merge symptoms, updating existing ones or adding new."""
    result = list(existing)
    for ns in new:
        matched = False
        for i, es in enumerate(result):
            if _similar(ns.name, es.name) > settings.question_similarity_threshold:
                # Merge fields — prefer non-None new values
                result[i] = Symptom(
                    name=ns.name or es.name,
                    duration=ns.duration or es.duration,
                    severity=ns.severity or es.severity,
                    character=ns.character or es.character,
                    location=ns.location or es.location,
                    onset=ns.onset or es.onset,
                    radiation=ns.radiation or es.radiation,
                    time_course=ns.time_course or es.time_course,
                    aggravating=_dedup_strings(es.aggravating, ns.aggravating),
                    relieving=_dedup_strings(es.relieving, ns.relieving),
                    associated=_dedup_strings(es.associated, ns.associated),
                )
                matched = True
                break
        if not matched:
            result.append(ns)
    return result


def _dedup_medications(existing: list[Medication], new: list[Medication]) -> list[Medication]:
    result = list(existing)
    for nm in new:
        if not any(_similar(nm.name, em.name) > settings.question_similarity_threshold for em in result):
            result.append(nm)
    return result


def _dedup_vitals(existing: list[VitalSign], new: list[VitalSign]) -> list[VitalSign]:
    result = list(existing)
    for nv in new:
        replaced = False
        for i, ev in enumerate(result):
            if _similar(nv.name, ev.name) > settings.question_similarity_threshold:
                result[i] = nv  # Update with latest value
                replaced = True
                break
        if not replaced:
            result.append(nv)
    return result


def _merge_ros(
    existing: dict[str, list[str]], new: dict[str, list[str]]
) -> dict[str, list[str]]:
    result = dict(existing)
    for system, findings in new.items():
        if system in result:
            result[system] = _dedup_strings(result[system], findings)
        else:
            result[system] = findings
    return result


def _merge_demographics(
    existing: DemographicsData,
    new: DemographicsData,
) -> DemographicsData:
    return DemographicsData(
        name=new.name or existing.name,
        age=new.age or existing.age,
        sex=new.sex or existing.sex,
        other=_dedup_strings(existing.other, new.other),
    )


def _merge_chief_complaint_structured(
    existing: ChiefComplaintStructured,
    new: ChiefComplaintStructured,
) -> ChiefComplaintStructured:
    return ChiefComplaintStructured(
        primary=new.primary or existing.primary,
        duration=new.duration or existing.duration,
        onset=new.onset or existing.onset,
        site=new.site or existing.site,
        character=new.character or existing.character,
        radiation=new.radiation or existing.radiation,
        severity=new.severity or existing.severity,
        time_course=new.time_course or existing.time_course,
        characteristics=_dedup_strings(existing.characteristics, new.characteristics),
        associated=_dedup_strings(existing.associated, new.associated),
        aggravating=_dedup_strings(existing.aggravating, new.aggravating),
        relieving=_dedup_strings(existing.relieving, new.relieving),
    )


def _merge_symptom_focuses(
    existing: list[SymptomFocus],
    new: list[SymptomFocus],
) -> list[SymptomFocus]:
    result = list(existing)
    for ns in new:
        matched = False
        for i, es in enumerate(result):
            if _similar(ns.canonical_name, es.canonical_name) > settings.question_similarity_threshold:
                first_seen_turn = es.first_seen_turn or ns.first_seen_turn
                if es.first_seen_turn and ns.first_seen_turn:
                    first_seen_turn = min(es.first_seen_turn, ns.first_seen_turn)
                result[i] = SymptomFocus(
                    canonical_name=ns.canonical_name or es.canonical_name,
                    aliases=_dedup_strings(es.aliases, ns.aliases),
                    first_seen_turn=first_seen_turn,
                    priority=ns.priority or es.priority,
                )
                matched = True
                break
        if not matched:
            result.append(ns)
    return result


def _resolve_symptom_key(existing: dict[str, object], key: str) -> str | None:
    if key in existing:
        return key

    for existing_key in existing:
        if _similar(existing_key, key) > settings.question_similarity_threshold:
            return existing_key
    return None


def _merge_symptom_known_info_record(
    existing: SymptomKnownInfo,
    new: SymptomKnownInfo,
) -> SymptomKnownInfo:
    return SymptomKnownInfo(
        duration=new.duration or existing.duration,
        onset=new.onset or existing.onset,
        location=new.location or existing.location,
        character=new.character or existing.character,
        radiation=new.radiation or existing.radiation,
        severity=new.severity or existing.severity,
        time_course=new.time_course or existing.time_course,
        associated=_dedup_strings(existing.associated, new.associated),
        aggravating=_dedup_strings(existing.aggravating, new.aggravating),
        relieving=_dedup_strings(existing.relieving, new.relieving),
        negatives=_dedup_strings(existing.negatives, new.negatives),
        red_flags=_dedup_strings(existing.red_flags, new.red_flags),
        notes=_dedup_strings(existing.notes, new.notes),
        last_updated_turn=max(existing.last_updated_turn, new.last_updated_turn),
    )


def _merge_symptom_known_info_map(
    existing: dict[str, SymptomKnownInfo],
    new: dict[str, SymptomKnownInfo],
) -> dict[str, SymptomKnownInfo]:
    result = dict(existing)
    for symptom_key, incoming in new.items():
        existing_key = _resolve_symptom_key(result, symptom_key)
        if existing_key is None:
            result[symptom_key] = incoming
        else:
            result[existing_key] = _merge_symptom_known_info_record(result[existing_key], incoming)
    return result


def _merge_symptom_keyword_state_record(
    existing: SymptomKeywordState,
    new: SymptomKeywordState,
) -> SymptomKeywordState:
    return SymptomKeywordState(
        symptom=new.symptom or existing.symptom,
        addressed_keywords=_dedup_strings(existing.addressed_keywords, new.addressed_keywords),
        new_keywords=_dedup_strings(existing.new_keywords, new.new_keywords),
        active_keywords=(
            _dedup_strings(existing.active_keywords, new.active_keywords)
            if not new.active_keywords
            else new.active_keywords
        ),
        rationale=new.rationale or existing.rationale,
        priority=new.priority or existing.priority,
    )


def _merge_symptom_keyword_state_map(
    existing: dict[str, SymptomKeywordState],
    new: dict[str, SymptomKeywordState],
) -> dict[str, SymptomKeywordState]:
    result = dict(existing)
    for symptom_key, incoming in new.items():
        existing_key = _resolve_symptom_key(result, symptom_key)
        if existing_key is None:
            result[symptom_key] = incoming
        else:
            result[existing_key] = _merge_symptom_keyword_state_record(
                result[existing_key],
                incoming,
            )
    return result


class EncounterState:
    """Manages accumulative encounter state with merge logic."""

    def __init__(self) -> None:
        self.data = EncounterStateData()
        self.transcript_lines: list[str] = []

    @property
    def full_transcript(self) -> str:
        return "\n".join(self.transcript_lines)

    def append_transcript(self, text: str) -> None:
        """Add new transcript text."""
        if text.strip():
            self.transcript_lines.append(text.strip())

    def merge(self, new_data: EncounterStateData) -> None:
        """Merge newly extracted data into the accumulative state."""
        d = self.data

        d.demographics = _merge_demographics(d.demographics, new_data.demographics)
        d.chief_complaint_structured = _merge_chief_complaint_structured(
            d.chief_complaint_structured,
            new_data.chief_complaint_structured,
        )

        # Simple fields — prefer new non-None values
        if new_data.chief_complaint:
            d.chief_complaint = new_data.chief_complaint
        elif not d.chief_complaint and d.chief_complaint_structured.primary:
            d.chief_complaint = d.chief_complaint_structured.primary
        if new_data.history_of_present_illness:
            d.history_of_present_illness = new_data.history_of_present_illness

        # List fields with dedup
        d.symptoms = _dedup_symptoms(d.symptoms, new_data.symptoms)
        d.past_medical_history = _dedup_strings(d.past_medical_history, new_data.past_medical_history)
        d.medications = _dedup_medications(d.medications, new_data.medications)
        d.allergies = _dedup_strings(d.allergies, new_data.allergies)
        d.family_history = _dedup_strings(d.family_history, new_data.family_history)
        d.social_history = _dedup_strings(d.social_history, new_data.social_history)
        d.physical_exam_findings = _dedup_strings(d.physical_exam_findings, new_data.physical_exam_findings)
        d.domains_covered = _dedup_strings(d.domains_covered, new_data.domains_covered)
        d.red_flags = _dedup_strings(d.red_flags, new_data.red_flags)
        d.isolated_symptoms = _merge_symptom_focuses(d.isolated_symptoms, new_data.isolated_symptoms)

        # Structured merges
        d.vitals = _dedup_vitals(d.vitals, new_data.vitals)
        d.review_of_systems = _merge_ros(d.review_of_systems, new_data.review_of_systems)
        d.symptom_known_info = _merge_symptom_known_info_map(
            d.symptom_known_info,
            new_data.symptom_known_info,
        )
        d.symptom_keyword_state = _merge_symptom_keyword_state_map(
            d.symptom_keyword_state,
            new_data.symptom_keyword_state,
        )

    def reset(self) -> None:
        """Reset for a new encounter."""
        self.data = EncounterStateData()
        self.transcript_lines = []
