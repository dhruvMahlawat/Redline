import re
import time
from google.genai import errors

RETRYABLE_CODES = {429, 500, 502, 503, 504}


def call_with_retry(func, max_attempts: int = 3, default_delay: float = 20.0):
    """Calls func() and retries on Gemini's free-tier rate limit (429) or a
    transient server overload (5xx) - both are "try again shortly", not a real
    bug. Anything else raises immediately, since retrying won't fix a real bug."""
    for attempt in range(max_attempts):
        try:
            return func()
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES or attempt == max_attempts - 1:
                raise
            delay = _extract_retry_delay(e) or default_delay
            time.sleep(delay + 1)  # +1s buffer so we don't fire right on the edge


def _extract_retry_delay(error) -> float | None:
    match = re.search(r"retry in ([\d.]+)s", str(error))
    return float(match.group(1)) if match else None
