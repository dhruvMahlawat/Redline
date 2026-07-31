from google import genai
from pydantic import BaseModel
from .retry import call_with_retry

EXTRACTION_MODEL = "gemini-3.6-flash"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    return _client


class Fact(BaseModel):
    field: str        # e.g. "monthly_rent", "security_deposit", "notice_period_days", "auto_renewal"
    value: str         # kept as plain text ("$2,400", "90 days") 
    source_quote: str  


class RedFlag(BaseModel):
    description: str
    source_quote: str
    severity: str  # "low" | "medium" | "high"


class ExtractionResult(BaseModel):
    facts: list[Fact]
    red_flags: list[RedFlag]


PROMPT = """You are reviewing a residential lease. Extract the following facts if present:
monthly_rent, security_deposit, notice_period_days, auto_renewal, late_fee.

Also flag anything a tenant should double check: unusual fees, one-sided termination terms,
auto-renewal traps, deposit terms that seem to favor the landlord, or anything vague.

For every fact AND every red flag, include the exact sentence from the lease it came from
in source_quote - copy it verbatim, don't paraphrase it. If a fact isn't in the lease, leave it out.

Lease text:
---
{lease_text}
---
"""


def extract_facts(lease_text: str) -> ExtractionResult:
    response = call_with_retry(lambda: _get_client().models.generate_content(
        model=EXTRACTION_MODEL,
        contents=PROMPT.format(lease_text=lease_text),
        config={
            "response_mime_type": "application/json",
            "response_schema": ExtractionResult,
        },
    ))
    return response.parsed
