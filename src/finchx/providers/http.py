"""Small, conservative HTTP defaults shared by real Providers.

This module deliberately does not implement proxy rotation, browser
fingerprinting, cookie handling, request scheduling, or retries.  Those are
not part of the Provider boundary.
"""

from __future__ import annotations

from collections.abc import Mapping


DEFAULT_TIMEOUT_SECONDS = 15.0

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
