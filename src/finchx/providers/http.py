"""Small, conservative HTTP defaults and transient retry policy.

This module deliberately does not implement proxy rotation, browser
fingerprinting, cookie handling, or request scheduling.  Retries are limited
to a single short retry for transient transport, timeout, rate-limit, and
server errors; schema, authentication, and request failures are not retried.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from time import sleep
from typing import Callable, TypeVar

from finchx.providers.errors import ProviderError


DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 0.25

ResultT = TypeVar("ResultT")

# A stable browser-shaped UA is already used by the verified Tencent, Sohu,
# and SZSE requests.  Keep it fixed; do not rotate it per request.
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def build_headers(
    *,
    accept: str | None = None,
    referer: str | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return defaults plus explicit Provider-specific header changes.

    Header names are merged case-insensitively so a Provider can deliberately
    replace a default while still adding a source-specific header.  Referer is
    never part of the global defaults.
    """

    headers = dict(DEFAULT_HEADERS)
    overrides: dict[str, str] = {}
    if accept is not None:
        overrides["Accept"] = accept
    if referer is not None:
        overrides["Referer"] = referer
    if extra is not None:
        overrides.update(extra)

    for key, value in overrides.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("HTTP header names must be non-empty strings")
        if not isinstance(value, str):
            raise TypeError("HTTP header values must be strings")
        for existing in tuple(headers):
            if existing.casefold() == key.casefold():
                del headers[existing]
        headers[key] = value
    return headers


def http_status_failure_reason(status_code: int) -> str | None:
    """Describe a non-success HTTP status without treating it as empty data."""

    if 200 <= status_code < 300:
        return None
    if status_code == 401:
        return "HTTP 401 (authentication required)"
    if status_code == 403:
        return "HTTP 403 (upstream refused the request)"
    if status_code == 429:
        return "HTTP 429 (upstream rate limit)"
    if 500 <= status_code < 600:
        return f"HTTP {status_code} (upstream server error)"
    return f"HTTP {status_code}"


def call_with_transient_retries(
    operation: Callable[[], ResultT],
    *,
    max_retries: int = DEFAULT_RETRIES,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    sleeper: Callable[[float], None] = sleep,
) -> ResultT:
    """Run a Provider operation with bounded retries for transient failures.

    Provider adapters usually run through ``Collector`` which owns its retry
    policy. Direct query services use this helper for their paginated calls so
    a flaky page does not discard the whole search. User errors and malformed
    source data pass through immediately.
    """

    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer")
    if (
        not isinstance(retry_delay_seconds, (int, float))
        or isinstance(retry_delay_seconds, bool)
        or not math.isfinite(float(retry_delay_seconds))
        or retry_delay_seconds < 0
    ):
        raise ValueError("retry_delay_seconds must be a finite non-negative number")
    if not callable(sleeper):
        raise TypeError("sleeper must be callable")
    for retry_index in range(max_retries + 1):
        try:
            return operation()
        except Exception as exc:
            if retry_index >= max_retries or not _is_transient_failure(exc):
                raise
            if retry_delay_seconds > 0:
                sleeper(float(retry_delay_seconds))
    raise AssertionError("retry loop exited without a result or exception")


def _is_transient_failure(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return True
    if not isinstance(error, ProviderError):
        return False
    reason = error.reason.casefold()
    status_match = re.search(r"\bhttp\s+(\d{3})\b", reason)
    if status_match is not None:
        status_code = int(status_match.group(1))
        if status_code == 429 or 500 <= status_code < 600:
            return True
    return any(
        marker in reason
        for marker in (
            "transport failure",
            "transport failed",
            "timed out",
            "timeout",
            "rate limit",
            "server error",
            "upstream unavailable",
            "source unavailable",
        )
    )
