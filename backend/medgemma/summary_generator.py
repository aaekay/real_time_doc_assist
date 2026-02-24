"""Role 5: Generate SOAP note from encounter using MedGemma."""

import json
import logging

from backend.models import EncounterStateData, SOAPNote
from backend.medgemma.client import chat_completion
from backend.medgemma.json_utils import clean_json_response
from backend.prompts import SUMMARY_SYSTEM, SUMMARY_USER

logger = logging.getLogger(__name__)


async def generate_soap_note(
    transcript: str,
    encounter_state: EncounterStateData,
) -> SOAPNote:
    """Generate a SOAP note summary for the encounter."""
    prompt = SUMMARY_USER.format(
        transcript=transcript,
        encounter_state=encounter_state.model_dump_json(indent=2),
    )

    raw = await chat_completion(
        system_prompt=SUMMARY_SYSTEM,
        user_prompt=prompt,
        max_tokens=1024,
        call_type="soap_summary",
    )

    try:
        cleaned = clean_json_response(raw)
        data = json.loads(cleaned)
        return SOAPNote(**data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse SOAP note, retrying: %s", e)
        raw = await chat_completion(
            system_prompt=SUMMARY_SYSTEM,
            user_prompt=prompt + "\n\nIMPORTANT: Output ONLY valid JSON, no other text.",
            max_tokens=1024,
            call_type="soap_summary",
        )
        try:
            cleaned = clean_json_response(raw)
            data = json.loads(cleaned)
            return SOAPNote(**data)
        except (json.JSONDecodeError, ValueError):
            logger.error("SOAP note generation failed after retry.")
            return SOAPNote(
                subjective="Unable to generate — parsing failed.",
                objective="N/A",
                assessment="N/A",
                plan="N/A",
            )
