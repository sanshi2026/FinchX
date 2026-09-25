from __future__ import annotations

import pytest

from finchx.contracts import Source
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers import ProviderError, TencentQuoteProvider
from finchx.providers.http import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    call_with_transient_retries,
    http_status_failure_reason,
)
from finchx.providers.tencent import _TencentHttpResponse


def _instrument() -> InstrumentId:
    return InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )


class _ResponseTransport:
    def __init__(self, response: _TencentHttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "params": dict(params),
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_defaults_are_stable_and_provider_headers_override_or_extend_them():
    headers = build_headers(
        accept="application/json",
        referer="https://provider.example/",
        extra={"user-agent": "Provider UA", "X-Provider-Mode": "fixture"},
    )

    assert DEFAULT_HEADERS["User-Agent"].startswith("Mozilla/5.0")
    assert headers["user-agent"] == "Provider UA"
    assert "User-Agent" not in headers
    assert headers["Accept"] == "application/json"
    assert headers["Referer"] == "https://provider.example/"
    assert headers["X-Provider-Mode"] == "fixture"
    assert "Connection" not in DEFAULT_HEADERS


def test_provider_sends_default_headers_and_bounded_timeout():
    transport = _ResponseTransport(_TencentHttpResponse(401, ""))
    provider = TencentQuoteProvider(transport=transport)

    with pytest.raises(ProviderError, match="HTTP 401"):
        provider.fetch_raw_quote(_instrument())

    call = transport.calls[0]
    headers = call["headers"]
    assert headers["User-Agent"] == DEFAULT_HEADERS["User-Agent"]
    assert headers["Accept"] == DEFAULT_HEADERS["Accept"]
    assert headers["Accept-Language"] == DEFAULT_HEADERS["Accept-Language"]
    assert headers["Referer"] == "https://finance.qq.com/"
    assert call["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS


@pytest.mark.parametrize("status_code", [401, 403, 429, 500, 503])
def test_http_failures_are_not_empty_data(status_code: int):
    transport = _ResponseTransport(_TencentHttpResponse(status_code, "[]"))
    provider = TencentQuoteProvider(transport=transport)

    with pytest.raises(ProviderError, match=f"HTTP {status_code}"):
        provider.fetch_raw_quote(_instrument())


@pytest.mark.parametrize("failure", [TimeoutError("read timeout"), ConnectionError("connection reset")])
def test_transport_timeout_and_network_failure_are_provider_failures(failure: Exception):
    provider = TencentQuoteProvider(transport=_ResponseTransport(failure))

    with pytest.raises(ProviderError, match="transport failure"):
        provider.fetch_raw_quote(_instrument())


def test_status_policy_classifies_success_and_failure():
    assert http_status_failure_reason(200) is None
    assert "HTTP 401" in http_status_failure_reason(401)
    assert "HTTP 403" in http_status_failure_reason(403)
    assert "HTTP 429" in http_status_failure_reason(429)
    assert "HTTP 500" in http_status_failure_reason(500)


def test_transient_retry_retries_server_errors_once_after_a_short_delay():
    source = Source(providerId="test.provider", sourceUrl="https://example.com/")
    calls = []
    delays = []

    def operation():
        calls.append(None)
        if len(calls) == 1:
            raise ProviderError(source, "HTTP 503 (upstream server error)")
        return "ok"

    result = call_with_transient_retries(operation, sleeper=delays.append)

    assert result == "ok"
    assert len(calls) == 2
    assert delays == [0.25]


@pytest.mark.parametrize("reason", [
    "HTTP 401 (authentication required)",
    "HTTP 403 (upstream refused the request)",
    "HTTP 400",
    "response schema drift",
])
def test_transient_retry_does_not_repeat_auth_request_or_schema_errors(reason: str):
    error = ProviderError(
        Source(providerId="test.provider", sourceUrl="https://example.com/"),
        reason,
    )
    calls = []

    def operation():
        calls.append(None)
        raise error

    with pytest.raises(ProviderError):
        call_with_transient_retries(operation, sleeper=lambda _delay: None)

    assert len(calls) == 1
