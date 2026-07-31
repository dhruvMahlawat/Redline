"""
Runs the full pipeline (parse -> extract -> verify) against the fixtures in
eval/fixtures/ and checks the results against eval/labels.json.

Needs a real GEMINI_API_KEY set (this makes actual API calls - it's not free,
though the fixtures are small so it's a handful of cents at most).

Usage: python3 eval/run_eval.py
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pipeline.parser import parse_pdf
from pipeline.extractor import extract_facts
from pipeline.verifier import verify_extraction

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
LABELS_PATH = os.path.join(os.path.dirname(__file__), "labels.json")
SECONDS_BETWEEN_FIXTURES = 15  # free tier allows 5 req/min; each fixture uses 2 calls


def normalize_number(value: str) -> str | None:
    """Strips $ , and whitespace so '$1,800' and '1800' compare equal."""
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return digits or None


def find_fact(facts: list[dict], field: str) -> dict | None:
    return next((f for f in facts if f["field"] == field), None)


def run():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY isn't set - add it to .env before running this.")
        return

    with open(LABELS_PATH) as f:
        labels = json.load(f)

    total_checks = 0
    correct_checks = 0
    high_confidence_count = 0
    high_confidence_correct = 0

    print(f"{'fixture':<38} {'field':<20} {'expected':<10} {'got':<10} {'confidence':<14} {'match'}")
    print("-" * 100)

    for i, (filename, expected) in enumerate(labels.items()):
        if i > 0:
            time.sleep(SECONDS_BETWEEN_FIXTURES)

        path = os.path.join(FIXTURES_DIR, filename)
        with open(path, "rb") as f:
            file_bytes = f.read()

        parsed = parse_pdf(file_bytes)
        extraction = extract_facts(parsed["full_text"])
        verified = verify_extraction(parsed["full_text"], extraction, parsed["page_breaks"])

        for field in ("monthly_rent", "security_deposit"):
            expected_value = normalize_number(expected.get(field))
            fact = find_fact(verified["facts"], field)
            got_value = normalize_number(fact["value"]) if fact else None
            confidence = fact["confidence"] if fact else "not_found"

            is_match = got_value == expected_value
            total_checks += 1
            correct_checks += int(is_match)

            if confidence == "high":
                high_confidence_count += 1
                high_confidence_correct += int(is_match)

            print(f"{filename:<38} {field:<20} {str(expected_value):<10} {str(got_value):<10} {confidence:<14} {'✓' if is_match else '✗'}")

        if expected.get("expected_red_flags") is None:
            print(f"{filename:<38} {'red_flags':<20} {'manual review':<10} {len(verified['red_flags']):<10}")
        else:
            print(f"{filename:<38} {'red_flags found':<20} {expected['expected_red_flags']:<10} {len(verified['red_flags']):<10}")

        for flag in verified["red_flags"]:
            print(f"    -> [{flag['severity']}, {flag['confidence']}] {flag['description']}")

        print()

    print("-" * 100)
    print(f"Field accuracy: {correct_checks}/{total_checks} ({100 * correct_checks / total_checks:.0f}%)")

    if high_confidence_count:
        false_confidence_rate = 100 * (1 - high_confidence_correct / high_confidence_count)
        print(f"Of {high_confidence_count} facts marked 'high confidence', "
              f"{high_confidence_correct} were actually correct "
              f"({false_confidence_rate:.0f}% false-confidence rate)")
    else:
        print("No facts were marked high confidence - nothing to report here.")


if __name__ == "__main__":
    run()
