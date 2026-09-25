from datetime import date, datetime, timezone
import builtins
import sys
from types import SimpleNamespace

import pytest

from finchx import FinchX
from finchx.collector import CachePolicy, Collector, MissingOptionalDependency
from finchx.datasets import MARKET_DAILY_REPLAY_DATASET, MarketDailyReplayRequest
from finchx.providers.errors import ProviderError
from finchx.providers.jiuyangongshe_replay import (
    JiyangongsheReplayProvider,
    _PlaywrightJiyangongsheTransport,
)
from finchx.storage import Cache, MemoryStorage


CANARY = "session-canary-must-not-escape"
CAPTURED_AT = datetime(2026, 9, 22, 1, 0, tzinfo=timezone.utc)


def _capture(requested_date: date, *, count_code: int = 0, field_data=None):
    return SimpleNamespace(
        count_document={
            "msg": "ok",
            "errCode": count_code,
            "data": {"all": 0, "date": requested_date.isoformat(), "recommend": 0},
            "serverTime": 0,
        },
        field_document={
            "msg": "ok",
            "errCode": 0,
            "data": [] if field_data is None else field_data,
            "serverTime": 0,
        },
        count_request_date=requested_date,
        field_request_date=requested_date,
        field_url="https://web-api.jiuyangongshe.com/jystock-app/api/v1/action/field",
    )


class RecordingTransport:
    def __init__(self, capture=None, error=None):
        self.capture = capture
        self.error = error
        self.calls = []

    def fetch(self, requested_date, *, timeout_seconds):
        self.calls.append((requested_date, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.capture


def _provider(transport):
    return JiyangongsheReplayProvider(transport=transport, clock=lambda: CAPTURED_AT)


def test_daily_replay_requires_explicit_keyword_only_session_and_keeps_business_result_clean():
    requested = MarketDailyReplayRequest(requestedDate="2026-09-18")
    transport = RecordingTransport(_capture(requested.requested_date))
    provider = _provider(transport)

    with pytest.raises(TypeError):
        provider.fetch_replay(requested)

    row = provider.fetch_replay(requested, session=CANARY)
    assert transport.calls == [(date(2026, 9, 18), 15.0)]
    assert not hasattr(provider, "_session")
    assert CANARY not in repr(row)


@pytest.mark.parametrize("value", [None, 123, "", "   "])
def test_invalid_sessions_fail_before_transport_without_echoing_value(value):
    transport = RecordingTransport(_capture(date(2026, 9, 18)))
    provider = _provider(transport)

    with pytest.raises(ProviderError) as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=value,
        )

    assert transport.calls == []
    assert CANARY not in str(caught.value)
    assert "session" in str(caught.value).lower()


def test_environment_variable_is_not_an_authentication_fallback(monkeypatch):
    monkeypatch.setenv("JYGS_SESSION", CANARY)
    provider = _provider(RecordingTransport(_capture(date(2026, 9, 18))))

    with pytest.raises(TypeError):
        provider.fetch_replay(MarketDailyReplayRequest(requestedDate="2026-09-18"))


@pytest.mark.parametrize("count_code, expected", [(1, "errCode=1"), (110, "errCode=110")])
def test_source_authentication_errors_remain_strict_and_redacted(count_code, expected):
    provider = _provider(RecordingTransport(_capture(date(2026, 9, 18), count_code=count_code)))

    with pytest.raises(ProviderError, match=expected) as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert CANARY not in str(caught.value)


def test_transport_exception_does_not_leak_session():
    provider = _provider(RecordingTransport(error=RuntimeError(CANARY)))

    with pytest.raises(ProviderError) as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert CANARY not in str(caught.value)
    assert caught.value.__context__ is None


def test_missing_playwright_is_a_public_optional_dependency_error(monkeypatch):
    real_import = builtins.__import__

    def block_playwright(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ModuleNotFoundError("No module named 'playwright'", name="playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_playwright)
    provider = JiyangongsheReplayProvider(clock=lambda: CAPTURED_AT)

    with pytest.raises(MissingOptionalDependency, match=r"finchx\[jygs\]") as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert caught.value.dependency == "playwright"
    assert CANARY not in str(caught.value)

    with pytest.raises(MissingOptionalDependency, match=r"finchx\[jygs\]") as collected:
        Collector().fetch(
            MARKET_DAILY_REPLAY_DATASET,
            provider="jiuyangongshe.daily_replay",
            request=MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert CANARY not in str(collected.value)


def test_missing_chromium_has_safe_install_hint_without_session_leak(monkeypatch):
    class FakeSyncPlaywright:
        def __enter__(self):
            return SimpleNamespace(
                chromium=SimpleNamespace(
                    launch=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(CANARY))
                )
            )

        def __exit__(self, *_args):
            return None

    fake_api = SimpleNamespace(
        TimeoutError=type("FakePlaywrightTimeoutError", (Exception,), {}),
        sync_playwright=lambda: FakeSyncPlaywright(),
    )
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_api)
    provider = JiyangongsheReplayProvider(clock=lambda: CAPTURED_AT)

    with pytest.raises(ProviderError, match=r"python -m playwright install chromium") as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert CANARY not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("failure", ["http", "json", "schema"])
def test_source_http_json_and_schema_failures_remain_strict(failure):
    capture = _capture(date(2026, 9, 18))
    if failure == "http":
        capture.count_document["_http_status"] = 401
    elif failure == "json":
        capture.field_document = {"_malformed": True}
    else:
        capture.count_document["unexpected"] = True
    provider = _provider(RecordingTransport(capture))

    with pytest.raises(ProviderError) as caught:
        provider.fetch_replay(
            MarketDailyReplayRequest(requestedDate="2026-09-18"),
            session=CANARY,
        )

    assert CANARY not in str(caught.value)


def test_playwright_transport_scopes_session_to_fresh_context_cookies(monkeypatch):
    class FakePage:
        def on(self, *_args):
            return None

        def goto(self, *_args, **_kwargs):
            return None

        def wait_for_timeout(self, _milliseconds):
            return None

    class FakeContext:
        def __init__(self):
            self.cookies = None

        def add_cookies(self, cookies):
            self.cookies = cookies

        def new_page(self):
            return FakePage()

        def close(self):
            return None

    context = FakeContext()

    class FakeBrowser:
        def new_context(self):
            return context

        def close(self):
            return None

    class FakePlaywright:
        chromium = SimpleNamespace(launch=lambda **_kwargs: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *_args):
            return None

    fake_api = SimpleNamespace(
        TimeoutError=type("FakePlaywrightTimeoutError", (Exception,), {}),
        sync_playwright=lambda: FakeSyncPlaywright(),
    )
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_api)

    with pytest.raises(RuntimeError):
        _provider_transport = _PlaywrightJiyangongsheTransport(CANARY)
        _provider_transport.fetch(date(2026, 9, 18), timeout_seconds=0.001)

    assert context.cookies == [
        {"name": "SESSION", "value": CANARY, "domain": "www.jiuyangongshe.com", "path": "/"},
        {"name": "SESSION", "value": CANARY, "domain": "web-api.jiuyangongshe.com", "path": "/"},
    ]


def test_client_and_collector_keep_session_out_of_request_cache_result_provenance_attempts_and_dicts():
    class RecordingProvider(JiyangongsheReplayProvider):
        sessions = []

        def fetch_replay(self, request, *, session):
            self.sessions.append(session)
            return super().fetch_replay(request, session=session)

    transport = RecordingTransport(_capture(date(2026, 9, 18)))
    provider = RecordingProvider(transport=transport, clock=lambda: CAPTURED_AT)
    cache = Cache(MemoryStorage(), clock=lambda: CAPTURED_AT)
    collector = Collector(
        provider_factories={provider.provider_id: lambda: provider},
        cache=cache,
        cache_policy={"market.daily_replay@1.0": CachePolicy(enabled=True)},
        clock=lambda: CAPTURED_AT,
    )
    fx = FinchX(collector=collector)

    first = fx.market.daily_replay("2026-09-18", session=CANARY)
    second = fx.market.daily_replay("2026-09-18", session="another-session", use_cache=True)
    refreshed = fx.market.daily_replay("2026-09-18", session="fresh-session", use_cache=False)

    assert first.data.source.provider_id == provider.provider_id
    assert second.cache_hit is True
    assert refreshed.cache_hit is False
    assert provider.sessions == [CANARY, "fresh-session"]
    assert len(transport.calls) == 2
    assert first.provenance[0].provider_id == provider.provider_id
    assert all(CANARY not in repr(value) for value in (first, second, refreshed))
    assert all(CANARY not in repr(attempt) for attempt in first.attempts)
    assert all(CANARY not in repr(value) for value in first.to_dicts())
    assert first.to_dicts()[0]["requestedDate"] == "2026-09-18"

    request = MarketDailyReplayRequest(requestedDate="2026-09-18")
    key_a = collector._cache_key(
        MARKET_DAILY_REPLAY_DATASET, {"request": request, "session": CANARY}
    )
    key_b = collector._cache_key(
        MARKET_DAILY_REPLAY_DATASET, {"request": request, "session": "another-session"}
    )
    assert key_a == key_b
    assert CANARY not in repr(key_a)


def test_client_rejects_invalid_session_before_collector():
    class FailingCollector:
        def fetch(self, *args, **kwargs):
            raise AssertionError("collector must not be called")

    fx = FinchX(collector=FailingCollector())
    for value, error_type in ((None, TypeError), (123, TypeError), ("", ValueError), (" ", ValueError)):
        with pytest.raises(error_type):
            fx.market.daily_replay("2026-09-18", session=value)
