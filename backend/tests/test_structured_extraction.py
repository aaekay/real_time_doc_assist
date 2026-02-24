import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.models import ChiefComplaintStructured, EncounterStateData
from backend.medgemma.structured_extraction import (
    extract_chief_complaint,
    extract_demographics,
)


class StructuredExtractionTests(unittest.TestCase):
    def test_extract_demographics_parses_response(self) -> None:
        mock_response = """
        {
          "demographics": {
            "name": "Ravi",
            "age": "42",
            "sex": "male",
            "other": ["teacher"]
          }
        }
        """

        with patch(
            "backend.medgemma.structured_extraction.chat_completion",
            new=AsyncMock(return_value=mock_response),
        ):
            demographics = asyncio.run(
                extract_demographics("patient: I am Ravi, 42-year-old male")
            )

        self.assertEqual(demographics.name, "Ravi")
        self.assertEqual(demographics.age, "42")
        self.assertEqual(demographics.sex, "male")
        self.assertEqual(demographics.other, ["teacher"])

    def test_extract_demographics_retries_on_invalid_json(self) -> None:
        with patch(
            "backend.medgemma.structured_extraction.chat_completion",
            new=AsyncMock(
                side_effect=[
                    "not-json",
                    '{"demographics":{"name":"Anita","age":"50","sex":"female","other":[]}}',
                ]
            ),
        ) as mock_call:
            demographics = asyncio.run(
                extract_demographics("patient: I am Anita, 50-year-old female")
            )

        self.assertEqual(demographics.name, "Anita")
        self.assertEqual(demographics.age, "50")
        self.assertEqual(mock_call.await_count, 2)

    def test_extract_chief_complaint_parses_response(self) -> None:
        mock_response = """
        {
          "chief_complaint": "Fever",
          "chief_complaint_structured": {
            "primary": "Fever",
            "duration": "5 days",
            "characteristics": ["high grade"],
            "associated": ["chills"]
          }
        }
        """

        with patch(
            "backend.medgemma.structured_extraction.chat_completion",
            new=AsyncMock(return_value=mock_response),
        ):
            chief, structured = asyncio.run(
                extract_chief_complaint("patient: fever for 5 days with chills")
            )

        self.assertEqual(chief, "Fever")
        self.assertEqual(structured.primary, "Fever")
        self.assertEqual(structured.duration, "5 days")
        self.assertEqual(structured.characteristics, ["high grade"])
        self.assertEqual(structured.associated, ["chills"])

    def test_extract_chief_complaint_falls_back_to_previous_on_failure(self) -> None:
        previous = EncounterStateData(
            chief_complaint="Fever",
            chief_complaint_structured=ChiefComplaintStructured(
                primary="Fever",
                duration="2 days",
                characteristics=["intermittent"],
                associated=["body ache"],
            ),
        )

        with patch(
            "backend.medgemma.structured_extraction.chat_completion",
            new=AsyncMock(side_effect=["not-json", "still-not-json"]),
        ):
            chief, structured = asyncio.run(
                extract_chief_complaint(
                    "patient: still fever",
                    previous_state=previous,
                )
            )

        self.assertEqual(chief, "Fever")
        self.assertEqual(structured.primary, "Fever")
        self.assertEqual(structured.duration, "2 days")
        self.assertEqual(structured.characteristics, ["intermittent"])
        self.assertEqual(structured.associated, ["body ache"])


if __name__ == "__main__":
    unittest.main()
