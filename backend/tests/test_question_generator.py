import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.medgemma.fixed_symptom_keywords import get_fixed_keywords_for_symptom
from backend.models import (
    EncounterStateData,
    KeywordSuggestionGroup,
    SymptomFocus,
    SymptomKeywordPipelineResult,
    SymptomKeywordState,
    SymptomKnownInfo,
)
from backend.medgemma.question_generator import (
    _generate_symptom_keyword_update,
    generate_keyword_suggestions,
    generate_keyword_suggestions_with_state,
)


class QuestionGeneratorPipelineTests(unittest.TestCase):
    def test_generate_keyword_suggestions_wrapper_returns_groups(self) -> None:
        with patch(
            "backend.medgemma.question_generator.generate_keyword_suggestions_with_state",
            new=AsyncMock(
                return_value=SymptomKeywordPipelineResult(
                    groups=[
                        KeywordSuggestionGroup(
                            category="fever",
                            priority="high",
                            keywords=["grade"],
                            rationale="Clarify fever profile.",
                        )
                    ]
                )
            ),
        ):
            groups = asyncio.run(generate_keyword_suggestions(EncounterStateData(), transcript="test"))

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].category, "fever")

    def test_fallback_when_no_symptoms_isolated(self) -> None:
        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=[]),
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    EncounterStateData(),
                    transcript="Doctor: tell me more",
                )
            )

        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.groups[0].category, "General Clarification")
        self.assertTrue(len(result.groups[0].keywords) > 0)

    def test_hard_replace_removes_addressed_and_adds_new(self) -> None:
        state = EncounterStateData(
            symptom_keyword_state={
                "fever": SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    active_keywords=["grade", "pattern", "chills"],
                )
            }
        )

        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=[SymptomFocus(canonical_name="fever")]),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_summary_delta",
            new=AsyncMock(return_value=SymptomKnownInfo()),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_keyword_update",
            new=AsyncMock(
                return_value=SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    addressed_keywords=["grade", "chills"],
                    new_keywords=["rigors"],
                )
            ),
        ), patch(
            "backend.medgemma.question_generator.get_fixed_keywords_for_symptom",
            return_value=[],
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    state,
                    transcript="patient has fever",
                )
            )

        self.assertEqual(result.groups[0].category, "fever")
        self.assertEqual(result.groups[0].keywords, ["pattern", "rigors"])
        self.assertEqual(
            result.symptom_keyword_state["fever"].active_keywords,
            ["pattern", "rigors"],
        )

    def test_groups_follow_latest_transcript_mention_order(self) -> None:
        isolated = [
            SymptomFocus(canonical_name="cough"),
            SymptomFocus(canonical_name="fever"),
        ]

        async def keyword_side_effect(
            symptom_name: str,
            transcript: str,
            known_info: SymptomKnownInfo,
            previous_active_keywords: list[str],
            baseline_fixed_keywords: list[str],
        ) -> SymptomKeywordState:
            return SymptomKeywordState(
                symptom=symptom_name,
                priority="high",
                addressed_keywords=[],
                new_keywords=[f"{symptom_name}-keyword"],
            )

        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=isolated),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_summary_delta",
            new=AsyncMock(return_value=SymptomKnownInfo()),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_keyword_update",
            new=AsyncMock(side_effect=keyword_side_effect),
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    EncounterStateData(),
                    transcript="Patient has fever first, and cough later",
                )
            )

        self.assertEqual([group.category for group in result.groups], ["cough", "fever"])

    def test_fixed_fever_keywords_seeded_when_unaddressed(self) -> None:
        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=[SymptomFocus(canonical_name="fever")]),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_summary_delta",
            new=AsyncMock(return_value=SymptomKnownInfo()),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_keyword_update",
            new=AsyncMock(
                return_value=SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    addressed_keywords=[],
                    new_keywords=[],
                )
            ),
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    EncounterStateData(),
                    transcript="patient has fever",
                )
            )

        expected_fixed = get_fixed_keywords_for_symptom("fever")
        self.assertEqual(result.groups[0].category, "fever")
        self.assertEqual(result.groups[0].keywords, expected_fixed)
        self.assertEqual(result.symptom_keyword_state["fever"].active_keywords, expected_fixed)

    def test_fixed_keywords_removed_when_addressed(self) -> None:
        state = EncounterStateData(
            symptom_keyword_state={
                "fever": SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    active_keywords=get_fixed_keywords_for_symptom("fever"),
                )
            }
        )

        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=[SymptomFocus(canonical_name="fever")]),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_summary_delta",
            new=AsyncMock(return_value=SymptomKnownInfo()),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_keyword_update",
            new=AsyncMock(
                return_value=SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    addressed_keywords=["grade", "respiratory symptoms"],
                    new_keywords=[],
                )
            ),
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    state,
                    transcript="fever with no respiratory symptoms",
                )
            )

        self.assertEqual(
            result.groups[0].keywords,
            ["duration", "temperature", "chills", "rigor", "pattern", "any GI symptoms"],
        )

    def test_fixed_and_model_keywords_are_deduped(self) -> None:
        with patch(
            "backend.medgemma.question_generator.isolate_symptoms",
            new=AsyncMock(return_value=[SymptomFocus(canonical_name="fever")]),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_summary_delta",
            new=AsyncMock(return_value=SymptomKnownInfo()),
        ), patch(
            "backend.medgemma.question_generator._generate_symptom_keyword_update",
            new=AsyncMock(
                return_value=SymptomKeywordState(
                    symptom="fever",
                    priority="high",
                    addressed_keywords=[],
                    new_keywords=["grade", "pattern", "travel history"],
                )
            ),
        ):
            result = asyncio.run(
                generate_keyword_suggestions_with_state(
                    EncounterStateData(),
                    transcript="patient has fever",
                )
            )

        self.assertEqual(
            result.groups[0].keywords,
            get_fixed_keywords_for_symptom("fever") + ["travel history"],
        )

    def test_keyword_update_filters_baseline_duplicates_and_includes_prompt_context(self) -> None:
        with patch(
            "backend.medgemma.question_generator._chat_json_with_retry",
            new=AsyncMock(
                return_value={
                    "symptom": "fever",
                    "priority": "high",
                    "rationale": "Need unresolved specifics only.",
                    "addressed_keywords": [],
                    "new_keywords": [
                        "grade",
                        "respiratory symptoms",
                        "travel history",
                    ],
                }
            ),
        ) as chat_mock:
            result = asyncio.run(
                _generate_symptom_keyword_update(
                    symptom_name="fever",
                    transcript="patient has fever",
                    known_info=SymptomKnownInfo(),
                    previous_active_keywords=["duration"],
                    baseline_fixed_keywords=["grade", "any respiratory symptoms"],
                )
            )

        self.assertEqual(result.new_keywords, ["travel history"])
        self.assertEqual(result.priority, "high")
        self.assertEqual(result.rationale, "Need unresolved specifics only.")
        user_prompt = chat_mock.await_args.kwargs["user_prompt"]
        self.assertIn("Baseline fixed keywords for this symptom", user_prompt)
        self.assertIn('"grade"', user_prompt)
        self.assertIn('"any respiratory symptoms"', user_prompt)


if __name__ == "__main__":
    unittest.main()
