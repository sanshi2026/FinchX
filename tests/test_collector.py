from datetime import date, datetime, timezone

import pytest

from finchx.collector import (
    AllProvidersFailed,
    AuthenticationError,
    Collector,
    FetchResult,
    InvalidRequest,
    MissingOptionalDependency,
    NoData,
    ProviderDoesNotSupportDataset,
    ProviderExecutionError,
    RateLimitError,
    RoutingPolicy,
    SchemaDrift,
    SourceUnavailable,
    Timeout,
    UnknownDataset,
    UnknownProvider,
)
from finchx.contracts import Source, StandardRecord
from finchx.datasets import (
    DatasetDefinition,
    TRADING_CALENDAR_DATASET,
    TradingCalendarRequest,
)
from finchx.entities import Market
from finchx.providers import (
    DatasetRoutingSemantics,
    PmcTradingCalendarProvider,
    ProviderError,
    ProviderRegistry,
    ProviderSpec,
)


class FakeRequest:
    pass


class FakeData:
    pass


FAKE_DATASET = DatasetDefinition(
    name="test.collector",
    schema_version="1.0",
    request_type=FakeRequest,
    data_type=FakeData,
)


class FirstProvider:
    calls: list[dict[str, object]] = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return {"provider": "first", "kwargs": kwargs}


class SecondProvider:
    calls: list[dict[str, object]] = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return {"provider": "second", "kwargs": kwargs}


def _fake_registry(*, first=FirstProvider, second=SecondProvider):
    return ProviderRegistry(
        (
            ProviderSpec("fake.first", first, (FAKE_DATASET,)),
            ProviderSpec("fake.second", second, (FAKE_DATASET,)),
        )
    )


def setup_function():
    FirstProvider.calls = []
    SecondProvider.calls = []


def test_default_and_explicit_provider_routing_preserve_fetch_kwargs():
    collector = Collector(registry=_fake_registry())

    default_result = collector.fetch(
        "test.collector@1.0", symbol="000001", limit=3
    )
    explicit_result = collector.fetch(
        FAKE_DATASET, provider="fake.second", symbol="000002"
    )

    assert default_result.provider == "fake.first"
    assert default_result.dataset is FAKE_DATASET
    assert default_result.data["provider"] == "first"
    assert FirstProvider.calls == [{"symbol": "000001", "limit": 3}]
    assert explicit_result.provider_id == "fake.second"
    assert explicit_result.data == {
        "provider": "second",
        "kwargs": {"symbol": "000002"},
    }


def test_unknown_and_unsupported_routes_fail_without_substitution():
    collector = Collector(registry=_fake_registry())

    with pytest.raises(UnknownDataset, match="unknown dataset"):
        collector.fetch("does.not.exist@1.0")
    with pytest.raises(UnknownProvider, match="unknown provider"):
        collector.fetch(FAKE_DATASET, provider="fake.missing")

    other_dataset = DatasetDefinition(
        name="test.other",
        schema_version="1.0",
        request_type=FakeRequest,
        data_type=FakeData,
    )
    other_registry = ProviderRegistry(
        (
            ProviderSpec("fake.only", FirstProvider, (other_dataset,)),
            ProviderSpec("fake.target", SecondProvider, (FAKE_DATASET,)),
        )
    )
    with pytest.raises(ProviderDoesNotSupportDataset, match="does not support"):
        Collector(registry=other_registry).fetch(
            FAKE_DATASET, provider="fake.only"
        )


class FailingFirstProvider:
    def fetch(self, **kwargs):
        raise RuntimeError("first provider failed")


def test_provider_failure_is_wrapped_once_and_never_falls_back():
    collector = Collector(
        registry=_fake_registry(first=FailingFirstProvider),
    )

    with pytest.raises(ProviderExecutionError, match="first provider failed"):
        collector.fetch(FAKE_DATASET, value=1)
    assert SecondProvider.calls == []


class ProviderErrorProvider:
    def fetch(self, **kwargs):
        raise ProviderError(Source(providerId="fake.first"), "provider parse failure")


def test_provider_error_is_not_hidden_or_reclassified():
    registry = _fake_registry(first=ProviderErrorProvider)
    with pytest.raises(ProviderError, match="provider parse failure"):
        Collector(registry=registry).fetch(FAKE_DATASET)


class MissingDependencyProvider:
    def __init__(self):
        raise ModuleNotFoundError("No module named 'fake_optional'", name="fake_optional")


def test_optional_dependency_error_identifies_provider_and_dependency():
    registry = ProviderRegistry(
        (
            ProviderSpec(
                "fake.optional",
                MissingDependencyProvider,
                (FAKE_DATASET,),
                optional_dependencies=("fake_optional",),
            ),
        )
    )
    with pytest.raises(MissingOptionalDependency, match="fake_optional"):
        Collector(registry=registry).fetch(FAKE_DATASET)


def test_fetch_result_is_a_small_envelope_around_standard_records():
    captured_at = datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc)
    provider_at = datetime(2026, 9, 20, 9, 29, tzinfo=timezone.utc)
    provider = PmcTradingCalendarProvider(clock=lambda: provider_at)
    collector = Collector(
        provider_instances={"pandas_market_calendars": provider},
        clock=lambda: captured_at,
    )

    result = collector.fetch(
        "trading_calendar@1.0",
        provider="pandas_market_calendars",
        request=TradingCalendarRequest(
            market=Market.CN_A,
            startDate=date(2026, 9, 18),
            endDate=date(2026, 9, 19),
        ),
    )

    assert isinstance(result, FetchResult)
    assert result.dataset is TRADING_CALENDAR_DATASET
    assert result.provider == "pandas_market_calendars"
    assert result.captured_at == captured_at
    assert result.provenance[0].provider_id == "pandas_market_calendars"
    assert result.data
    assert all(isinstance(record, StandardRecord) for record in result.data)
    assert {record.dataset for record in result.data} == {"trading_calendar"}
    assert {record.captured_at for record in result.data} == {provider_at}


def test_single_source_semantics_remain_registry_bound():
    registry = ProviderRegistry(
        (
            ProviderSpec(
                "fake.single",
                FirstProvider,
                (FAKE_DATASET,),
                routing_semantics={
                    FAKE_DATASET.name: DatasetRoutingSemantics.SINGLE_SOURCE
                },
            ),
        )
    )
    collector = Collector(registry=registry)
    assert collector.fetch(FAKE_DATASET).provider == "fake.single"
    assert registry.routing_semantics_for(FAKE_DATASET) is DatasetRoutingSemantics.SINGLE_SOURCE


class ScriptedProvider:
    def __init__(self):
        self.outcomes: list[object] = []
        self.calls = 0

    def fetch(self, **kwargs):
        self.calls += 1
        if not self.outcomes:
            return {"calls": self.calls, "kwargs": kwargs}
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class ScriptedProviderA(ScriptedProvider):
    pass


class ScriptedProviderB(ScriptedProvider):
    pass


class ScriptedProviderC(ScriptedProvider):
    pass


def _scripted_registry(*, single_source=False):
    semantics = (
        {FAKE_DATASET.name: DatasetRoutingSemantics.SINGLE_SOURCE}
        if single_source
        else {}
    )
    return ProviderRegistry(
        (
            ProviderSpec(
                "fake.a",
                ScriptedProviderA,
                (FAKE_DATASET,),
                routing_semantics=semantics,
            ),
            ProviderSpec(
                "fake.b",
                ScriptedProviderB,
                (FAKE_DATASET,),
                routing_semantics=semantics,
            ),
            ProviderSpec(
                "fake.c",
                ScriptedProviderC,
                (FAKE_DATASET,),
                routing_semantics=semantics,
            ),
        )
    )


def _scripted_collector(*, policy=None, single_source=False):
    providers = {provider_id: ScriptedProvider() for provider_id in ("fake.a", "fake.b", "fake.c")}
    return (
        Collector(
            registry=_scripted_registry(single_source=single_source),
            provider_instances=providers,
            policy=policy,
        ),
        providers,
    )


def test_timeout_and_rate_limit_retry_the_same_provider_without_fallback():
    delays: list[float] = []
    collector, providers = _scripted_collector(
        policy=RoutingPolicy(
            max_retries=1,
            retry_delay_seconds=0.25,
            sleeper=delays.append,
        )
    )
    providers["fake.a"].outcomes = [Timeout("slow"), {"ok": True}]

    result = collector.fetch(FAKE_DATASET, provider="fake.a")

    assert result.provider == "fake.a"
    assert result.fallback_used is False
    assert providers["fake.a"].calls == 2
    assert [(attempt.provider, attempt.attempt, attempt.success) for attempt in result.attempts] == [
        ("fake.a", 1, False),
        ("fake.a", 2, True),
    ]
    assert delays == [0.25]

    providers["fake.a"].outcomes = [RateLimitError("limited"), {"ok": "rate"}]
    second = collector.fetch(FAKE_DATASET, provider="fake.a")
    assert second.data == {"ok": "rate"}
    assert providers["fake.a"].calls == 4
    assert delays == [0.25, 0.25]


def test_fallback_uses_explicit_policy_order_and_records_all_attempts():
    policy = RoutingPolicy(
        provider_order={FAKE_DATASET.name: ("fake.a", "fake.b", "fake.c")},
        max_retries=0,
    )
    collector, providers = _scripted_collector(policy=policy)
    providers["fake.a"].outcomes = [Timeout("a timeout")]
    providers["fake.b"].outcomes = [SourceUnavailable("b offline")]
    providers["fake.c"].outcomes = [{"provider": "c"}]

    result = collector.fetch(FAKE_DATASET)

    assert result.provider == "fake.c"
    assert result.fallback_used is True
    assert [attempt.provider for attempt in result.attempts] == [
        "fake.a",
        "fake.b",
        "fake.c",
    ]
    assert [providers[name].calls for name in ("fake.a", "fake.b", "fake.c")] == [1, 1, 1]


def test_explicit_provider_is_a_strict_pin_even_when_retry_is_allowed():
    policy = RoutingPolicy(
        provider_order={FAKE_DATASET.name: ("fake.a", "fake.b")},
        max_retries=1,
    )
    collector, providers = _scripted_collector(policy=policy)
    providers["fake.a"].outcomes = [Timeout("a timeout"), Timeout("still slow")]

    with pytest.raises(AllProvidersFailed):
        collector.fetch(FAKE_DATASET, provider="fake.a")

    assert providers["fake.a"].calls == 2
    assert providers["fake.b"].calls == 0


@pytest.mark.parametrize(
    "failure",
    [
        AuthenticationError("credentials required"),
        SchemaDrift("schema changed"),
        InvalidRequest("bad request"),
        MissingOptionalDependency("test.collector", "fake.a", "fake-package"),
    ],
)
def test_non_transient_errors_fail_fast_and_never_fallback(failure):
    policy = RoutingPolicy(max_retries=2)
    collector, providers = _scripted_collector(policy=policy)
    providers["fake.a"].outcomes = [failure]

    with pytest.raises(type(failure)):
        collector.fetch(FAKE_DATASET)

    assert providers["fake.a"].calls == 1
    assert providers["fake.b"].calls == 0
    assert providers["fake.c"].calls == 0


def test_no_data_can_fallback_for_an_interchangeable_dataset():
    policy = RoutingPolicy(max_retries=0)
    collector, providers = _scripted_collector(policy=policy)
    providers["fake.a"].outcomes = [NoData("no rows")]
    providers["fake.b"].outcomes = [{"provider": "b"}]

    result = collector.fetch(FAKE_DATASET)

    assert result.provider == "fake.b"
    assert result.fallback_used is True
    assert [attempt.success for attempt in result.attempts] == [False, True]


def test_single_source_never_falls_back_even_with_multiple_registered_providers():
    policy = RoutingPolicy(max_retries=0)
    collector, providers = _scripted_collector(policy=policy, single_source=True)
    providers["fake.a"].outcomes = [SourceUnavailable("offline")]

    with pytest.raises(AllProvidersFailed) as caught:
        collector.fetch(FAKE_DATASET)

    assert [attempt.provider for attempt in caught.value.attempts] == ["fake.a"]
    assert providers["fake.b"].calls == 0
    assert providers["fake.c"].calls == 0


def test_all_provider_failure_retains_attempt_context_and_safe_error_summary():
    policy = RoutingPolicy(max_retries=0)
    collector, providers = _scripted_collector(policy=policy)
    providers["fake.a"].outcomes = [SourceUnavailable("session=top-secret token=abc")]
    providers["fake.b"].outcomes = [SourceUnavailable("b offline")]
    providers["fake.c"].outcomes = [SourceUnavailable("c offline")]

    with pytest.raises(AllProvidersFailed) as caught:
        collector.fetch(FAKE_DATASET)

    error = caught.value
    assert error.providers == ("fake.a", "fake.b", "fake.c")
    assert len(error.attempts) == 3
    assert error.attempts[0].error_type == "SourceUnavailable"
    assert "top-secret" not in (error.attempts[0].error_message or "")
    assert "abc" not in (error.attempts[0].error_message or "")
