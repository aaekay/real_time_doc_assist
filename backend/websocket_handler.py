"""Core WebSocket orchestration: audio → MedASR → MedGemma pipeline → client."""

import asyncio
from contextlib import suppress
import json
import logging
import time
from typing import Awaitable, Callable

from fastapi import WebSocket, WebSocketDisconnect
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from backend.asr.audio_buffer import AudioBuffer
from backend.asr.medasr_transcriber import transcribe
from backend.config import settings
from backend.encounter.state import EncounterState
from backend.models import (
    ChiefComplaintStructured,
    DemographicsData,
    EncounterStateData,
    KeywordSuggestionGroup,
    SymptomKeywordPipelineResult,
    WSMessage,
    WSMessageType,
)
from backend.medgemma.structured_extraction import extract_chief_complaint, extract_demographics
from backend.medgemma.question_generator import generate_keyword_suggestions_with_state
from backend.medgemma.summary_generator import generate_soap_note

logger = logging.getLogger(__name__)


TRANSIENT_LLM_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)

ROLE_DEMOGRAPHICS = "demographics"
ROLE_CHIEF_COMPLAINT = "chief_complaint"
ROLE_KEYWORDS = "keywords"
PIPELINE_ROLES = (
    ROLE_DEMOGRAPHICS,
    ROLE_CHIEF_COMPLAINT,
    ROLE_KEYWORDS,
)


async def _send(ws: WebSocket, msg_type: WSMessageType, data: dict) -> None:
    """Send a typed JSON message to the client."""
    msg = WSMessage(type=msg_type, data=data)
    await ws.send_text(msg.model_dump_json())


def is_pipeline_stale(pipeline_epoch: int, session_epoch: int) -> bool:
    """Return True when a pipeline run no longer belongs to the active session."""
    return pipeline_epoch != session_epoch


def should_start_pipeline(
    *,
    transcript_snapshot: str,
    last_pipeline_transcript: str,
    now: float,
    next_pipeline_time: float,
    pipeline_task: asyncio.Task | None,
) -> bool:
    """Return True when the periodic pipeline should run on fresh transcript."""
    has_new_transcript = bool(
        transcript_snapshot and transcript_snapshot != last_pipeline_transcript
    )
    task_idle = pipeline_task is None or pipeline_task.done()
    return has_new_transcript and task_idle and now >= next_pipeline_time


def build_session_reset_payload() -> dict:
    """Canonical empty session snapshot for frontend reset."""
    return {
        "transcript": "",
        "keyword_suggestions": [],
        "encounter_state": EncounterStateData().model_dump(),
        "soap_note": None,
        "pipeline_latency_ms": None,
        "message": "Session reset.",
    }


def role_debounce_seconds() -> dict[str, float]:
    """Resolve per-role debounce intervals with fallback to global interval."""
    global_interval = max(0.0, settings.pipeline_debounce_seconds)

    def _value(role_value: float | None) -> float:
        if role_value is None:
            return global_interval
        return max(0.0, role_value)

    return {
        ROLE_DEMOGRAPHICS: _value(settings.demographics_pipeline_debounce_seconds),
        ROLE_CHIEF_COMPLAINT: _value(settings.chief_complaint_pipeline_debounce_seconds),
        ROLE_KEYWORDS: _value(
            settings.symptom_pipeline_debounce_seconds
            if settings.symptom_pipeline_debounce_seconds is not None
            else settings.keywords_pipeline_debounce_seconds
        ),
    }


async def _cancel_task(task: asyncio.Task | None, name: str) -> None:
    """Cancel a task and swallow cancellation errors."""
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    logger.info("Cancelled %s task.", name)


async def _cancel_role_tasks(tasks: list[asyncio.Task]) -> None:
    """Cancel outstanding per-role tasks."""
    pending = [task for task in tasks if not task.done()]
    if not pending:
        return
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


async def _cancel_pipeline_role_tasks(role_tasks: dict[str, asyncio.Task | None]) -> None:
    """Cancel role-specific pipeline tasks and clear task references."""
    for role, task in role_tasks.items():
        await _cancel_task(task, f"{role}_pipeline")
        role_tasks[role] = None


async def _run_role(
    role: str,
    role_call: Awaitable[object],
) -> tuple[str, object | None, Exception | None]:
    """Wrap a role call so result and errors can be handled uniformly."""
    try:
        result = await role_call
        return role, result, None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return role, None, exc


def _is_transient_role_error(error: Exception) -> bool:
    return isinstance(error, TRANSIENT_LLM_ERRORS)


async def _run_medgemma_pipeline(
    encounter: EncounterState,
    ws: WebSocket,
    pipeline_epoch: int,
    get_session_epoch: Callable[[], int],
    transcript_snapshot: str,
    state_snapshot: EncounterStateData,
    roles_to_run: set[str] | None = None,
) -> None:
    """Run selected MedGemma roles in parallel for a transcript snapshot."""
    start = time.time()
    role_tasks: list[asyncio.Task] = []
    selected_roles = set(roles_to_run) if roles_to_run is not None else set(PIPELINE_ROLES)

    try:
        if is_pipeline_stale(pipeline_epoch, get_session_epoch()):
            logger.info("Skipping stale pipeline run (epoch=%s).", pipeline_epoch)
            return

        role_calls: list[tuple[str, Awaitable[object]]] = []
        if ROLE_DEMOGRAPHICS in selected_roles and settings.enable_demographics_extraction:
            role_calls.append(
                (
                    ROLE_DEMOGRAPHICS,
                    extract_demographics(
                        transcript=transcript_snapshot,
                        previous_state=state_snapshot,
                    ),
                )
            )

        if ROLE_CHIEF_COMPLAINT in selected_roles:
            role_calls.append(
                (
                    ROLE_CHIEF_COMPLAINT,
                    extract_chief_complaint(
                        transcript=transcript_snapshot,
                        previous_state=state_snapshot,
                    ),
                )
            )

        if ROLE_KEYWORDS in selected_roles:
            role_calls.append(
                (
                    ROLE_KEYWORDS,
                    generate_keyword_suggestions_with_state(
                        state_snapshot,
                        transcript=transcript_snapshot,
                    ),
                )
            )

        if not role_calls:
            return

        role_tasks = [
            asyncio.create_task(_run_role(role, call))
            for role, call in role_calls
        ]
        failures = 0
        transient_failures = 0
        published_any = False

        for completed in asyncio.as_completed(role_tasks):
            role, result, error = await completed

            if error is not None:
                failures += 1
                if _is_transient_role_error(error):
                    transient_failures += 1
                    logger.warning("MedGemma %s role transient failure: %s", role, error)
                    logger.debug(
                        "Transient MedGemma %s traceback follows",
                        role,
                        exc_info=error,
                    )
                else:
                    logger.error("MedGemma %s role failed: %s", role, error, exc_info=error)
                continue

            if is_pipeline_stale(pipeline_epoch, get_session_epoch()):
                logger.info("Dropping stale %s output (epoch=%s).", role, pipeline_epoch)
                await _cancel_role_tasks(role_tasks)
                return

            if role == ROLE_DEMOGRAPHICS:
                if not isinstance(result, DemographicsData):
                    logger.error(
                        "Unexpected demographics payload type: %s",
                        type(result).__name__,
                    )
                    continue

                partial_state = EncounterStateData(demographics=result)
                encounter.merge(partial_state)
                await _send(ws, WSMessageType.ENCOUNTER_STATE, encounter.data.model_dump())
                published_any = True

            elif role == ROLE_CHIEF_COMPLAINT:
                if not isinstance(result, tuple) or len(result) != 2:
                    logger.error(
                        "Unexpected chief_complaint payload type: %s",
                        type(result).__name__,
                    )
                    continue
                chief_text, structured = result
                partial_state = EncounterStateData(
                    chief_complaint=chief_text,
                    chief_complaint_structured=structured or ChiefComplaintStructured(),
                )
                encounter.merge(partial_state)
                await _send(ws, WSMessageType.ENCOUNTER_STATE, encounter.data.model_dump())
                published_any = True

            elif role == ROLE_KEYWORDS:
                if not isinstance(result, SymptomKeywordPipelineResult):
                    logger.error(
                        "Unexpected keyword payload type: %s",
                        type(result).__name__,
                    )
                    continue

                partial_state = EncounterStateData(
                    isolated_symptoms=result.isolated_symptoms,
                    symptom_known_info=result.symptom_known_info,
                    symptom_keyword_state=result.symptom_keyword_state,
                )
                encounter.merge(partial_state)
                await _send(ws, WSMessageType.ENCOUNTER_STATE, encounter.data.model_dump())

                keyword_groups = [
                    item for item in result.groups if isinstance(item, KeywordSuggestionGroup)
                ]
                await _send(
                    ws,
                    WSMessageType.KEYWORD_SUGGESTIONS,
                    {"groups": [g.model_dump() for g in keyword_groups]},
                )
                published_any = True

        if failures == len(role_tasks) and not published_any:
            if transient_failures == failures:
                await _send(
                    ws,
                    WSMessageType.STATUS,
                    {
                        "message": (
                            "LLM temporarily unavailable. "
                            "Continuing and retrying on the next cycle."
                        )
                    },
                )
            else:
                await _send(
                    ws,
                    WSMessageType.ERROR,
                    {"message": "Pipeline error: all MedGemma role calls failed."},
                )

        await _cancel_role_tasks(role_tasks)
        role_tasks = []

        elapsed = time.time() - start
        await _send(ws, WSMessageType.STATUS, {"pipeline_latency_ms": int(elapsed * 1000)})
        logger.info(
            "MedGemma pipeline completed in %.1fs (selected_roles=%s, calls=%s, failures=%s)",
            elapsed,
            sorted(selected_roles),
            len(role_calls),
            failures,
        )

    except asyncio.CancelledError:
        await _cancel_role_tasks(role_tasks)
        logger.info("Pipeline task cancelled.")
        raise
    except Exception as e:
        await _cancel_role_tasks(role_tasks)
        logger.exception("MedGemma pipeline error: %s", e)
        await _send(ws, WSMessageType.ERROR, {"message": f"Pipeline error: {e}"})


async def handle_websocket(ws: WebSocket) -> None:
    """Main WebSocket handler for a single client session."""
    await ws.accept()
    logger.info("WebSocket client connected.")

    encounter = EncounterState()
    audio_buffer = AudioBuffer()
    role_intervals = role_debounce_seconds()
    role_tasks: dict[str, asyncio.Task | None] = {role: None for role in PIPELINE_ROLES}
    next_role_pipeline_time = {role: 0.0 for role in PIPELINE_ROLES}
    last_role_pipeline_transcript = {role: "" for role in PIPELINE_ROLES}
    session_epoch = 0
    medasr_not_loaded_reported = False

    try:
        def get_session_epoch() -> int:
            return session_epoch

        while True:
            message = await ws.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                logger.info("WebSocket client disconnected.")
                break

            # Binary = audio data
            if "bytes" in message and message["bytes"]:
                audio_buffer.add_pcm16(message["bytes"])

                chunk = audio_buffer.get_chunk()
                if chunk is not None:
                    # Transcribe with MedASR
                    try:
                        text = transcribe(chunk, settings.audio_sample_rate)
                    except Exception as e:
                        if isinstance(e, RuntimeError) and "MedASR not loaded" in str(e):
                            if not medasr_not_loaded_reported:
                                medasr_not_loaded_reported = True
                                app_state = getattr(getattr(ws, "app", None), "state", None)
                                medasr_startup_error = (
                                    getattr(app_state, "medasr_error", None) if app_state else None
                                )
                                logger.error(
                                    "MedASR unavailable in this worker: %r",
                                    e,
                                    exc_info=True,
                                )
                                await _send(
                                    ws,
                                    WSMessageType.ERROR,
                                    {
                                        "message": (
                                            "ASR unavailable: MedASR did not load on backend startup. "
                                            "Check /health and backend startup logs."
                                        ),
                                        "startup_error": medasr_startup_error,
                                    },
                                )
                            continue
                        logger.error(
                            "MedASR transcription error (%s): %r",
                            type(e).__name__,
                            e,
                            exc_info=True,
                        )
                        continue

                    if text:
                        encounter.append_transcript(text)
                        if settings.live_transcript_enabled:
                            await _send(
                                ws,
                                WSMessageType.TRANSCRIPT,
                                {"text": text, "full": encounter.full_transcript},
                            )

                        # Role-specific MedGemma pipelines with independent intervals,
                        # only when fresh transcript text exists per role.
                        now = time.time()
                        transcript_snapshot = encounter.full_transcript
                        for role in PIPELINE_ROLES:
                            if role == ROLE_DEMOGRAPHICS and not settings.enable_demographics_extraction:
                                continue

                            if should_start_pipeline(
                                transcript_snapshot=transcript_snapshot,
                                last_pipeline_transcript=last_role_pipeline_transcript[role],
                                now=now,
                                next_pipeline_time=next_role_pipeline_time[role],
                                pipeline_task=role_tasks[role],
                            ):
                                pipeline_epoch = session_epoch
                                state_snapshot = encounter.data.model_copy(deep=True)
                                role_tasks[role] = asyncio.create_task(
                                    _run_medgemma_pipeline(
                                        encounter=encounter,
                                        ws=ws,
                                        pipeline_epoch=pipeline_epoch,
                                        get_session_epoch=get_session_epoch,
                                        transcript_snapshot=transcript_snapshot,
                                        state_snapshot=state_snapshot,
                                        roles_to_run={role},
                                    )
                                )
                                last_role_pipeline_transcript[role] = transcript_snapshot
                                next_role_pipeline_time[role] = now + role_intervals[role]

            # Text = control messages
            elif "text" in message and message["text"]:
                try:
                    ctrl = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                action = ctrl.get("action")

                if action == "end_session":
                    session_epoch += 1
                    await _cancel_pipeline_role_tasks(role_tasks)
                    for role in PIPELINE_ROLES:
                        next_role_pipeline_time[role] = 0.0

                    # Generate SOAP note
                    await _send(ws, WSMessageType.STATUS, {"message": "Generating SOAP note..."})
                    soap = await generate_soap_note(
                        encounter.full_transcript,
                        encounter.data.model_copy(deep=True),
                    )
                    await _send(ws, WSMessageType.SOAP_NOTE, soap.model_dump())

                elif action == "reset":
                    session_epoch += 1
                    await _cancel_pipeline_role_tasks(role_tasks)
                    encounter.reset()
                    audio_buffer.reset()
                    for role in PIPELINE_ROLES:
                        next_role_pipeline_time[role] = 0.0
                        last_role_pipeline_transcript[role] = ""
                    await _send(
                        ws,
                        WSMessageType.SESSION_RESET,
                        build_session_reset_payload(),
                    )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        await _cancel_pipeline_role_tasks(role_tasks)
