"""Shared JSON cleanup helpers for model responses."""


def clean_json_response(text: str) -> str:
    """Strip markdown code fences and surrounding whitespace from JSON-like text."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
