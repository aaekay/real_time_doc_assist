"""Run each clinical vignette through the MedGemma pipeline and collect outputs."""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import EncounterStateData
from backend.medgemma.structured_extraction import extract_demographics, extract_chief_complaint
from backend.medgemma.question_generator import generate_keyword_suggestions

VIGNETTES_DIR = Path(__file__).parent / "vignettes"
RESULTS_DIR = Path(__file__).parent / "results"


def load_vignettes() -> list[dict]:
    """Load all vignette JSON files."""
    vignettes = []
    for f in sorted(VIGNETTES_DIR.glob("*.json")):
        with open(f) as fh:
            v = json.load(fh)
            v["_file"] = f.name
            vignettes.append(v)
    return vignettes


def dialogue_to_transcript(dialogue: list[dict]) -> str:
    """Convert dialogue turns to a transcript string."""
    lines = []
    for turn in dialogue:
        speaker = "Doctor" if turn["speaker"] == "doctor" else "Patient"
        lines.append(f"{speaker}: {turn['text']}")
    return "\n".join(lines)


async def evaluate_vignette(vignette: dict) -> dict:
    """Run the MedGemma pipeline on a single vignette."""
    transcript = dialogue_to_transcript(vignette["dialogue"])
    state = EncounterStateData()
    start = time.time()

    # Step 1: Extract demographics
    demographics = await extract_demographics(transcript)
    state.demographics = demographics

    # Step 2: Extract chief complaint
    chief_text, chief_structured = await extract_chief_complaint(transcript)
    state.chief_complaint = chief_text
    state.chief_complaint_structured = chief_structured

    # Step 3: Generate keyword suggestions
    keyword_groups = await generate_keyword_suggestions(state, transcript=transcript)

    elapsed = time.time() - start

    return {
        "vignette_id": vignette["id"],
        "vignette_file": vignette["_file"],
        "specialty": vignette["specialty"],
        "title": vignette["title"],
        "transcript": transcript,
        "encounter_state": state.model_dump(),
        "keyword_groups": [g.model_dump() for g in keyword_groups],
        "gold_standard_questions": vignette["gold_standard_questions"],
        "red_flag_questions": vignette["red_flag_questions"],
        "expected_domains": vignette["expected_domains"],
        "expected_consult": vignette["expected_consult"],
        "latency_seconds": elapsed,
    }


async def main():
    vignettes = load_vignettes()
    if not vignettes:
        print("No vignettes found in", VIGNETTES_DIR)
        return

    RESULTS_DIR.mkdir(exist_ok=True)
    results = []

    print(f"Running evaluation on {len(vignettes)} vignettes...")
    for i, v in enumerate(vignettes):
        print(f"  [{i+1}/{len(vignettes)}] {v['title']}...", end=" ", flush=True)
        try:
            result = await evaluate_vignette(v)
            results.append(result)
            print(f"done ({result['latency_seconds']:.1f}s)")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({
                "vignette_id": v["id"],
                "vignette_file": v["_file"],
                "error": str(e),
            })

    # Save results
    output_path = RESULTS_DIR / "evaluation_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Quick summary
    successful = [r for r in results if "error" not in r]
    if successful:
        latencies = [r["latency_seconds"] for r in successful]
        avg_latency = sum(latencies) / len(latencies)
        print(f"  Successful: {len(successful)}/{len(results)}")
        print(f"  Avg latency: {avg_latency:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
