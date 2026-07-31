import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
from google.genai import errors
from pipeline.retry import call_with_retry


def test_retries_on_429_rate_limit():
    err = errors.ClientError(429, {"error": {"message": "retry in 1s."}})
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise err
        return "ok"

    with patch("pipeline.retry.time.sleep"):
        assert call_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_retries_on_503_server_overload():
    # this is the exact error type hit in practice - a 503 with no explicit
    # retry-delay text, unlike the 429 case above
    err = errors.ServerError(503, {"error": {"message": "high demand, try again later."}})
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise err
        return "ok"

    with patch("pipeline.retry.time.sleep"):
        assert call_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_does_not_retry_non_api_errors():
    def broken():
        raise ValueError("a real bug")

    try:
        call_with_retry(broken)
        assert False, "should have raised"
    except ValueError:
        pass


def test_does_not_retry_non_transient_4xx():
    err = errors.ClientError(400, {"error": {"message": "bad request"}})

    def bad():
        raise err

    try:
        call_with_retry(bad)
        assert False, "should have raised"
    except errors.ClientError as e:
        assert e.code == 400


def test_gives_up_after_max_attempts_instead_of_hanging():
    err = errors.ServerError(503, {"error": {"message": "still down"}})

    def always_fails():
        raise err

    with patch("pipeline.retry.time.sleep"):
        try:
            call_with_retry(always_fails, max_attempts=3)
            assert False, "should have raised"
        except errors.ServerError as e:
            assert e.code == 503
