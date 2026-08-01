from google import genai
from pydantic import BaseModel
from .extractor import ExtractionResult
from .textmatch import find_quote
from .retry import call_with_retry

VERIFICATION_MODEL = "gemini-3.6-flash"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


class SupportCheck(BaseModel):
    index: int       # position in the list we sent, so we can match answers back up
    supported: bool
    reasoning: str


class SupportCheckResult(BaseModel):
    checks: list[SupportCheck]


VERIFY_PROMPT = """For each numbered claim below, check whether its quote actually supports it.
Answer strictly based on the quote text - if the quote is vague, unrelated, or contradicts
the claim, mark supported as false.

{items}
"""


def check_claims_supported(claims: list[dict]) -> list[SupportCheck]:
    """One batched call: does each quote actually support its claim?
    claims = [{"claim": "...", "quote": "..."}, ...]"""
    if not claims:
        return []

    items_text = "\n\n".join(
        f'{i}. Claim: "{c["claim"]}"\n   Quote: "{c["quote"]}"'
        for i, c in enumerate(claims)
    )

    response = call_with_retry(lambda: _get_client().models.generate_content(
        model=VERIFICATION_MODEL,
        contents=VERIFY_PROMPT.format(items=items_text),
        config={
            "response_mime_type": "application/json",
            "response_schema": SupportCheckResult,
        },
    ))
    return response.parsed.checks


def verify_extraction(document_text: str, extraction: ExtractionResult, page_breaks: list) -> dict:
    """Runs both checks on every fact and red flag, returns everything with a
    confidence label and page number attached. This is the step that turns
    'the AI said so' into 'the AI said so, and here's why that should be trusted
    or not, and here's where to check it yourself'."""
    from .parser import page_for_index

    claims = [{"claim": f"{f.field}: {f.value}", "quote": f.source_quote} for f in extraction.facts]
    claims += [{"claim": rf.description, "quote": rf.source_quote} for rf in extraction.red_flags]

    support_checks = check_claims_supported(claims)
    support_by_index = {c.index: c for c in support_checks}

    results = {"facts": [], "red_flags": []}
    index = 0

    for fact in extraction.facts:
        quote_exists, char_index = find_quote(fact.source_quote, document_text)
        check = support_by_index.get(index)
        results["facts"].append({
            **fact.model_dump(),
            "confidence": _confidence_label(quote_exists, check.supported if check else False),
            "reasoning": _reasoning_text(quote_exists, check),
            "page": page_for_index(char_index, page_breaks) if quote_exists else None,
        })
        index += 1

    for flag in extraction.red_flags:
        quote_exists, char_index = find_quote(flag.source_quote, document_text)
        check = support_by_index.get(index)
        results["red_flags"].append({
            **flag.model_dump(),
            "confidence": _confidence_label(quote_exists, check.supported if check else False),
            "reasoning": _reasoning_text(quote_exists, check),
            "page": page_for_index(char_index, page_breaks) if quote_exists else None,
        })
        index += 1

    return results


def _confidence_label(quote_exists: bool, supported: bool) -> str:
    if not quote_exists:
        return "low"      # quote doesn't appear in the document at all - likely invented
    if supported:
        return "high"
    return "medium"        # quote is real, but doesn't clearly back up the claim


def _reasoning_text(quote_exists: bool, check: SupportCheck | None) -> str:
    if not quote_exists:
        return "This quote wasn't found verbatim in the document."
    if check is None:
        return "Verification check didn't return a result for this item."
    return check.reasoning
