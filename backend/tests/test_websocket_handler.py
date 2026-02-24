import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.config import settings
from backend.encounter.state import EncounterState
from backend.models import (
    ChiefComplaintStructured,
    DemographicsData,
    KeywordSuggestionGroup,
    SymptomKeywordPipelineResult,
    SymptomKeywordState,
    WSMessageType,
)
from backend.websocket_handler import (
    _run_medgemma_pipeline,
    build_session_reset_payload,
    is_pipeline_stale,
    role_debounce_seconds,
    should_start_pipeline,
)


class _TaskStub:
    def __init__(self, done_state: bool) -> None:
        self._done_state = done_state

    def done(self) -> bool:
        return self._done_state


class WebSocketHandlerTests(unittest.TestCase):
    def test_session_reset_payload_shape(self) -> None:
        payload = build_session_reset_payload()

        self.assertEqual(payload["transcript"], "")
        self.assertEqual(payload["keyword_suggestions"], [])
        self.assertIn("encounter_state", payload)
        self.assertIsNone(payload["soap_note"])
        self.assertIsNone(payload["pipeline_latency_ms"])
        self.assertEqual(payload["message"], "Session reset.")

    def test_stale_pipeline_detection(self) -> None:
        self.assertTrue(is_pipeline_stale(1, 2))
        self.assertFalse(is_pipeline_stale(3, 3))

    def test_should_start_pipeline_with_new_transcript_and_idle_task(self) -> None:
        self.assertTrue(
            should_start_pipeline(
                transcript_snapshot="doctor: chest pain for 2 days",
                last_pipeline_transcript="doctor: chest pain",
                now=10.0,
                next_pipeline_time=5.0,
                pipeline_task=None,
            )
        )

    def test_should_not_start_pipeline_without_new_transcript(self) -> None:
        self.assertFalse(
            should_start_pipeline(
                transcript_snapshot="same text",
                last_pipeline_transcript="same text",
                now=10.0,
                next_pipeline_time=5.0,
                pipeline_task=None,
            )
        )

    def test_should_not_start_pipeline_before_interval_gate(self) -> None:
        self.assertFalse(
            should_start_pipeline(
                transcript_snapshot="new text",
                last_pipeline_transcript="old text",
                now=4.0,
                next_pipeline_time=5.0,
                pipeline_task=None,
            )
        )

    def test_should_not_start_pipeline_when_task_running(self) -> None:
        self.assertFalse(
            should_start_pipeline(
                transcript_snapshot="new text",
                last_pipeline_transcript="old text",
                now=10.0,
                next_pipeline_time=5.0,
                pipeline_task=_TaskStub(done_state=False),  # type: ignore[arg-type]
            )
        )

    def test_should_start_pipeline_when_previous_task_done(self) -> None:
        self.assertTrue(
            should_start_pipeline(
                transcript_snapshot="new text",
                last_pipeline_transcript="old text",
                now=10.0,
                next_pipeline_time=5.0,
                pipeline_task=_TaskStub(done_state=True),  # type: ignore[arg-type]
            )
        )

    def test_session_reset_enum_exists(self) -> None:
        self.assertEqual(WSMessageType.SESSION_RESET.value, "session_reset")

    def test_role_debounce_seconds_falls_back_to_global(self) -> None:
        with (
            patch.object(settings, "pipeline_debounce_seconds", 5.0),
            patch.object(settings, "demographics_pipeline_debounce_seconds", None),
            patch.object(settings, "chief_complaint_pipeline_debounce_seconds", None),
            patch.object(settings, "keywords_pipeline_debounce_seconds", None),
            patch.object(settings, "symptom_pipeline_debounce_seconds", None),
        ):
            intervals = role_debounce_seconds()

        self.assertEqual(intervals["demographics"], 5.0)
        self.assertEqual(intervals["chief_complaint"], 5.0)
        self.assertEqual(intervals["keywords"], 5.0)

    def test_role_debounce_seconds_uses_role_overrides(self) -> None:
        with (
            patch.object(settings, "pipeline_debounce_seconds", 5.0),
            patch.object(settings, "demographics_pipeline_debounce_seconds", 15.0),
            patch.object(settings, "chief_complaint_pipeline_debounce_seconds", 6.0),
            patch.object(settings, "keywords_pipeline_debounce_seconds", 2.0),
            patch.object(settings, "symptom_pipeline_debounce_seconds", None),
        ):
            intervals = role_debounce_seconds()

        self.assertEqual(intervals["demographics"], 15.0)
        self.assertEqual(intervals["chief_complaint"], 6.0)
        self.assertEqual(intervals["keywords"], 2.0)

    def test_run_pipeline_executes_roles_in_parallel(self) -> None:
        encounter = EncounterState()
        state_snapshot = encounter.data.model_copy(deep=True)
        ws = object()

        started: set[str] = set()
        gate = asyncio.Event()

        async def demographics_mock(*args, **kwargs):  # type: ignore[no-untyped-def]
            started.add("demographics")
            if len(started) == 3:
                gate.set()
            await gate.wait()
            return DemographicsData(name="Ravi", age="42", sex="male", other=[])

        async def chief_complaint_mock(*args, **kwargs):  # type: ignore[no-untyped-def]
            started.add("chief_complaint")
            if len(started) == 3:
                gate.set()
            await gate.wait()
            return ("fever", ChiefComplaintStructured(primary="fever", duration="5 days"))

        async def keywords_mock(*args, **kwargs):  # type: ignore[no-untyped-def]
            started.add("keywords")
            if len(started) == 3:
                gate.set()
            await gate.wait()
            return SymptomKeywordPipelineResult(
                groups=[
                    KeywordSuggestionGroup(
                        category="Fever",
                        priority="high",
                        keywords=["grade", "pattern"],
                        rationale="Clarify fever profile.",
                    )
                ],
                symptom_keyword_state={
                    "Fever": SymptomKeywordState(
                        symptom="Fever",
                        priority="high",
                        active_keywords=["grade", "pattern"],
                    )
                },
            )

        with (
            patch.object(settings, "enable_demographics_extraction", True),
            patch(
                "backend.websocket_handler.extract_demographics",
                new=AsyncMock(side_effect=demographics_mock),
            ),
            patch(
                "backend.websocket_handler.extract_chief_complaint",
                new=AsyncMock(side_effect=chief_complaint_mock),
            ),
            patch(
                "backend.websocket_handler.generate_keyword_suggestions_with_state",
                new=AsyncMock(side_effect=keywords_mock),
            ),
            patch("backend.websocket_handler._send", new=AsyncMock()) as send_mock,
        ):
            asyncio.run(
                asyncio.wait_for(
                    _run_medgemma_pipeline(
                        encounter=encounter,
                        ws=ws,  # type: ignore[arg-type]
                        pipeline_epoch=1,
                        get_session_epoch=lambda: 1,
                        transcript_snapshot="patient has fever for 5 days",
                        state_snapshot=state_snapshot,
                    ),
                    timeout=1.0,
                )
            )

        self.assertEqual(started, {"demographics", "chief_complaint", "keywords"})
        self.assertEqual(encounter.data.demographics.name, "Ravi")
        self.assertEqual(encounter.data.chief_complaint, "fever")
        sent_types = [call.args[1] for call in send_mock.await_args_list]
        self.assertIn(WSMessageType.KEYWORD_SUGGESTIONS, sent_types)
        self.assertIn(WSMessageType.ENCOUNTER_STATE, sent_types)
        self.assertIn(WSMessageType.STATUS, sent_types)

    def test_run_pipeline_allows_partial_success(self) -> None:
        encounter = EncounterState()
        state_snapshot = encounter.data.model_copy(deep=True)
        ws = object()

        with (
            patch.object(settings, "enable_demographics_extraction", True),
            patch(
                "backend.websocket_handler.extract_demographics",
                new=AsyncMock(side_effect=RuntimeError("demographics failed")),
            ),
            patch(
                "backend.websocket_handler.extract_chief_complaint",
                new=AsyncMock(side_effect=RuntimeError("chief complaint failed")),
            ),
            patch(
                "backend.websocket_handler.generate_keyword_suggestions_with_state",
                new=AsyncMock(
                    return_value=SymptomKeywordPipelineResult(
                        groups=[
                            KeywordSuggestionGroup(
                                category="Fever",
                                priority="high",
                                keywords=["pattern"],
                                rationale="Narrow differential.",
                            )
                        ],
                        symptom_keyword_state={
                            "Fever": SymptomKeywordState(
                                symptom="Fever",
                                priority="high",
                                active_keywords=["pattern"],
                            )
                        },
                    )
                ),
            ),
            patch("backend.websocket_handler._send", new=AsyncMock()) as send_mock,
        ):
            asyncio.run(
                _run_medgemma_pipeline(
                    encounter=encounter,
                    ws=ws,  # type: ignore[arg-type]
                    pipeline_epoch=1,
                    get_session_epoch=lambda: 1,
                    transcript_snapshot="patient reports fever",
                    state_snapshot=state_snapshot,
                )
            )

        self.assertIsNone(encounter.data.demographics.name)
        sent_types = [call.args[1] for call in send_mock.await_args_list]
        self.assertIn(WSMessageType.KEYWORD_SUGGESTIONS, sent_types)
        self.assertIn(WSMessageType.ENCOUNTER_STATE, sent_types)
        self.assertIn(WSMessageType.STATUS, sent_types)
        self.assertNotIn(WSMessageType.ERROR, sent_types)

    def test_run_pipeline_skips_demographics_when_disabled(self) -> None:
        encounter = EncounterState()
        state_snapshot = encounter.data.model_copy(deep=True)
        ws = object()

        with (
            patch.object(settings, "enable_demographics_extraction", False),
            patch(
                "backend.websocket_handler.extract_demographics",
                new=AsyncMock(return_value=DemographicsData(name="Ravi")),
            ) as demographics_mock,
            patch(
                "backend.websocket_handler.extract_chief_complaint",
                new=AsyncMock(
                    return_value=("fever", ChiefComplaintStructured(primary="fever")),
                ),
            ),
            patch(
                "backend.websocket_handler.generate_keyword_suggestions_with_state",
                new=AsyncMock(
                    return_value=SymptomKeywordPipelineResult(
                        groups=[
                            KeywordSuggestionGroup(
                                category="Fever",
                                priority="high",
                                keywords=["pattern"],
                                rationale="Narrow differential.",
                            )
                        ],
                        symptom_keyword_state={
                            "Fever": SymptomKeywordState(
                                symptom="Fever",
                                priority="high",
                                active_keywords=["pattern"],
                            )
                        },
                    )
                ),
            ),
            patch("backend.websocket_handler._send", new=AsyncMock()) as send_mock,
        ):
            asyncio.run(
                _run_medgemma_pipeline(
                    encounter=encounter,
                    ws=ws,  # type: ignore[arg-type]
                    pipeline_epoch=1,
                    get_session_epoch=lambda: 1,
                    transcript_snapshot="patient reports fever",
                    state_snapshot=state_snapshot,
                )
            )

        demographics_mock.assert_not_called()
        self.assertIsNone(encounter.data.demographics.name)
        sent_types = [call.args[1] for call in send_mock.await_args_list]
        self.assertIn(WSMessageType.KEYWORD_SUGGESTIONS, sent_types)
        self.assertIn(WSMessageType.ENCOUNTER_STATE, sent_types)  # chief_complaint/keywords publish state
        self.assertIn(WSMessageType.STATUS, sent_types)


if __name__ == "__main__":
    unittest.main()
