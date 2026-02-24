import unittest

from backend.medgemma.fixed_symptom_keywords import get_fixed_keywords_for_symptom


class FixedSymptomKeywordsTests(unittest.TestCase):
    def test_fever_keywords_present(self) -> None:
        keywords = get_fixed_keywords_for_symptom("fever")
        self.assertIn("duration", keywords)
        self.assertIn("grade", keywords)
        self.assertIn("any GI symptoms", keywords)

    def test_common_non_fever_symptoms_present(self) -> None:
        self.assertIn("sputum color", get_fixed_keywords_for_symptom("cough"))
        self.assertIn("focal deficits", get_fixed_keywords_for_symptom("headache"))
        self.assertIn("bladder bowel symptoms", get_fixed_keywords_for_symptom("back pain"))
        self.assertIn("mucosal involvement", get_fixed_keywords_for_symptom("rash"))

    def test_alias_resolution(self) -> None:
        self.assertEqual(
            get_fixed_keywords_for_symptom("pyrexia"),
            get_fixed_keywords_for_symptom("fever"),
        )
        self.assertEqual(
            get_fixed_keywords_for_symptom("dyspnea"),
            get_fixed_keywords_for_symptom("shortness of breath"),
        )
        self.assertEqual(
            get_fixed_keywords_for_symptom("diarrhoea"),
            get_fixed_keywords_for_symptom("diarrhea"),
        )

    def test_unknown_symptom_returns_empty_list(self) -> None:
        self.assertEqual(get_fixed_keywords_for_symptom("ear pain"), [])

    def test_lookup_returns_copy_not_reference(self) -> None:
        keywords = get_fixed_keywords_for_symptom("fever")
        keywords.append("dummy")
        self.assertNotIn("dummy", get_fixed_keywords_for_symptom("fever"))


if __name__ == "__main__":
    unittest.main()
