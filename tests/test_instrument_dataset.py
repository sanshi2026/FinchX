from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from finchx.contracts import DataStatus, ProvenanceClass, Source
from finchx.datasets import INSTRUMENT_DATASET, InstrumentData, InstrumentRequest
from finchx.datasets.instrument import _ProviderInstrumentRow, _normalize_provider_rows
from finchx.entities import (
    Exchange,
    InstrumentId,
    InstrumentKind,
    InvalidSymbolError,
    Market,
    format_symbol,
)
from finchx.providers import InstrumentProvider, ProviderError


@dataclass(frozen=True)
class _FakeNativeInstrument:
    ts_code: str
    market_code: str
    exchange_code: str | None
    security_type: str
    name: str
    source_id: str
    vendor_internal_code: str


class _FakeInstrumentProvider:
    def __init__(self, rows=(), *, failure=None):
        self._rows = tuple(rows)
        self._failure = failure
        self._source = Source(providerId="offline.fixture")

    @property
    def source(self):
        return self._source

    def fetch_instrument(self, request):
        if self._failure is not None:
            raise ProviderError(self.source, self._failure)
        return tuple(
            self._parse(row)
            for row in self._rows
            if row.ts_code == request.instrument_id.code
        )

    @staticmethod
    def _parse(row):
        markets = {"CN": "cn_a"}
        exchanges = {"SH": "sse", "SZ": "szse", "BJ": "bse"}
        kinds = {"STOCK": "equity", "INDEX": "index", "ETF": "etf"}
        return _ProviderInstrumentRow(
            code=row.ts_code,
            market=markets.get(row.market_code, row.market_code),
            exchange=exchanges.get(row.exchange_code, row.exchange_code),
            kind=kinds.get(row.security_type, row.security_type),
            name=row.name,
            source_record_id=row.source_id,
        )


class _FixedHandoffProvider:
    """Provider double that can expose incorrect or duplicate handoff rows."""

    def __init__(self, rows=()):
        self._rows = tuple(rows)
        self._source = Source(providerId="offline.fixture")

    @property
    def source(self):
        return self._source

    def fetch_instrument(self, request):
        return self._rows


def _captured_at():
    return datetime(2026, 9, 17, 9, 30, tzinfo=timezone(timedelta(hours=8)))


@pytest.mark.parametrize(
    ("identity", "native"),
    [
        (
            InstrumentId(
                code="600519",
                market=Market.CN_A,
                exchange=Exchange.SSE,
                kind=InstrumentKind.EQUITY,
            ),
            _FakeNativeInstrument(
                ts_code="600519",
                market_code="CN",
                exchange_code="SH",
                security_type="STOCK",
                name="贵州茅台",
                source_id="fixture-600519",
                vendor_internal_code="vendor-001",
            ),
        ),
        (
            InstrumentId(
                code="000001",
                market=Market.CN_A,
                exchange=Exchange.SZSE,
                kind=InstrumentKind.EQUITY,
            ),
            _FakeNativeInstrument(
                ts_code="000001",
                market_code="CN",
                exchange_code="SZ",
                security_type="STOCK",
                name="平安银行",
                source_id="fixture-000001",
                vendor_internal_code="vendor-002",
            ),
        ),
    ],
)
def test_instrument_dataset_definition_and_provider_normalization(identity, native):
    assert INSTRUMENT_DATASET.name == "instrument"
    assert INSTRUMENT_DATASET.request_type is InstrumentRequest
    assert INSTRUMENT_DATASET.data_type is InstrumentData
    assert INSTRUMENT_DATASET.schema_version == "1.0"

    request = InstrumentRequest(instrumentId=identity)
    provider: InstrumentProvider = _FakeInstrumentProvider([native])
    provider_rows = provider.fetch_instrument(request)
    records = _normalize_provider_rows(
        request,
        provider_rows,
        source=provider.source,
        captured_at=_captured_at(),
    )

    assert len(records) == 1
    record = records[0]
    assert record.dataset == INSTRUMENT_DATASET.name
    assert record.schema_version == INSTRUMENT_DATASET.schema_version
    assert record.entity_id == identity
    assert record.record_id == format_symbol(identity)
    assert record.data == {
        "instrumentId": identity.model_dump(mode="json"),
        "name": native.name,
    }
    assert InstrumentData.model_validate(record.data).instrument_id == identity
    assert record.source == Source(
        providerId="offline.fixture",
        sourceRecordId=native.source_id,
    )
    assert record.status is DataStatus.LIVE
    assert record.quality.issues == []
    assert record.provenance.record_class is ProvenanceClass.STANDARDIZED
    assert record.provenance.transformation_version == "instrument-normalizer/1"
    assert record.provenance.source_references == []

    wire_record = record.model_dump(mode="json", by_alias=True)
    wire_text = str(wire_record)
    for provider_field in (
        "ts_code",
        "market_code",
        "exchange_code",
        "security_type",
        "vendor_internal_code",
    ):
        assert provider_field not in wire_text


def test_instrument_request_requires_complete_instrument_identity():
    with pytest.raises(ValidationError):
        InstrumentRequest(instrumentId="600519")
    with pytest.raises(ValidationError):
        InstrumentRequest(instrumentId={"code": "600519"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("market_code", "CN_B"),
        ("exchange_code", "UNKNOWN"),
        ("security_type", "WARRANT"),
    ],
)
def test_unknown_provider_identity_tokens_fail_without_guessing(field, value):
    identity = InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    native_values = {
        "ts_code": "600519",
        "market_code": "CN",
        "exchange_code": "SH",
        "security_type": "STOCK",
        "name": "贵州茅台",
        "source_id": "fixture-unknown",
        "vendor_internal_code": "vendor-003",
    }
    native_values[field] = value
    provider: InstrumentProvider = _FakeInstrumentProvider(
        [_FakeNativeInstrument(**native_values)]
    )
    rows = provider.fetch_instrument(InstrumentRequest(instrumentId=identity))

    with pytest.raises(InvalidSymbolError):
        _normalize_provider_rows(
            InstrumentRequest(instrumentId=identity),
            rows,
            source=provider.source,
            captured_at=_captured_at(),
        )


def test_successful_empty_lookup_is_empty_and_provider_failure_is_an_error():
    identity = InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    request = InstrumentRequest(instrumentId=identity)
    provider: InstrumentProvider = _FakeInstrumentProvider()
    rows = provider.fetch_instrument(request)
    assert rows == ()
    assert _normalize_provider_rows(
        request,
        rows,
        source=provider.source,
        captured_at=_captured_at(),
    ) == ()

    failing_provider = _FakeInstrumentProvider(failure="offline fixture failure")
    with pytest.raises(ProviderError) as caught:
        failing_provider.fetch_instrument(request)
    assert caught.value.source == failing_provider.source
    assert caught.value.reason == "offline fixture failure"
    assert "offline fixture failure" in str(caught.value)


def test_instrument_payload_rejects_provider_only_fields():
    identity = InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    with pytest.raises(ValidationError):
        InstrumentData(
            instrumentId=identity,
            name="贵州茅台",
            vendor_internal_code="vendor-001",
        )


def test_exact_request_rejects_a_different_valid_identity():
    requested = InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    wrong_identity_row = _ProviderInstrumentRow(
        code="000001",
        market="cn_a",
        exchange="szse",
        kind="equity",
        name="平安银行",
    )
    provider: InstrumentProvider = _FixedHandoffProvider([wrong_identity_row])
    request = InstrumentRequest(instrumentId=requested)

    with pytest.raises(ValueError, match="outside the explicit request"):
        _normalize_provider_rows(
            request,
            provider.fetch_instrument(request),
            source=provider.source,
            captured_at=_captured_at(),
        )


def test_exact_request_rejects_multiple_matching_rows():
    identity = InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    row = _ProviderInstrumentRow(
        code="600519",
        market="cn_a",
        exchange="sse",
        kind="equity",
        name="贵州茅台",
    )
    provider: InstrumentProvider = _FixedHandoffProvider([row, row])
    request = InstrumentRequest(instrumentId=identity)

    with pytest.raises(ValueError, match="multiple rows for an exact instrument request"):
        _normalize_provider_rows(
            request,
            provider.fetch_instrument(request),
            source=provider.source,
            captured_at=_captured_at(),
        )


def test_explicitly_missing_exchange_remains_unspecified():
    identity = InstrumentId(
        code="000300",
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
    )
    native = _FakeNativeInstrument(
        ts_code="000300",
        market_code="CN",
        exchange_code=None,
        security_type="INDEX",
        name="沪深300指数",
        source_id="fixture-000300",
        vendor_internal_code="vendor-index",
    )
    provider: InstrumentProvider = _FakeInstrumentProvider([native])
    request = InstrumentRequest(instrumentId=identity)

    records = _normalize_provider_rows(
        request,
        provider.fetch_instrument(request),
        source=provider.source,
        captured_at=_captured_at(),
    )

    assert len(records) == 1
    assert records[0].entity_id.exchange is None


def test_public_exports_exclude_internal_provider_handoff_and_normalizer():
    import finchx.datasets as datasets_api
    import finchx.providers as providers_api

    assert set(datasets_api.__all__) == {
        "NEWS_DOCUMENT_DATASET",
        "NewsDocumentData",
        "NewsDocumentRef",
        "NewsSearchRequest",
        "MarketNewsSearchRequest",
        "NewsSourceOccurrence",
        "FINANCIAL_STATEMENT_DATASET",
        "FinancialStatementData",
        "FinancialStatementLineItem",
        "FinancialStatementPeriod",
        "FinancialStatementRequest",
        "DISCLOSURE_DOCUMENT_DATASET",
        "DisclosureAttachment",
        "DisclosureCategory",
        "DisclosureDocumentData",
        "DisclosureDocumentRef",
        "DisclosureSearchRequest",
        "MARKET_BREADTH_DATASET",
        "MARKET_LIMIT_UP_POOL_DATASET",
        "MARKET_LIMIT_DOWN_POOL_DATASET",
        "MARKET_YESTERDAY_LIMIT_UP_POOL_DATASET",
        "MARKET_STRONG_POOL_DATASET",
        "MARKET_BROKEN_LIMIT_POOL_DATASET",
        "MarketBreadthBucket",
        "MarketBreadthData",
        "MarketBreadthDistributionEntry",
        "MarketBreadthRequest",
        "MarketLimitUpPoolData",
        "MarketLimitUpPoolRequest",
        "MarketLimitUpStats",
        "MarketLimitDownPoolData",
        "MarketLimitDownPoolRequest",
        "MarketYesterdayLimitUpPoolData",
        "MarketYesterdayLimitUpPoolRequest",
        "MarketStrongPoolData",
        "MarketStrongPoolRequest",
        "StrongPoolSelectionReason",
        "MarketBrokenLimitPoolData",
        "MarketBrokenLimitPoolRequest",
        "ChangePercentRankingMetric",
        "DatasetDefinition",
        "DatasetId",
        "INSTRUMENT_DATASET",
        "InstrumentData",
        "InstrumentRequest",
        "InstrumentUniverse",
        "InstrumentUniverseRequest",
        "MARKET_KLINES_DATASET",
        "MARKET_FUND_FLOW_DAILY_DATASET",
        "MARKET_FUND_FLOW_INTRADAY_DATASET",
        "MARKET_FUND_FLOW_SNAPSHOT_DATASET",
        "MARKET_INSTRUMENT_SECTOR_SNAPSHOT_DATASET",
        "MARKET_INDUSTRY_COMPARISON_DATASET",
        "FUNDAMENTAL_COMPANY_PROFILE_DATASET",
        "FUNDAMENTAL_FINANCIAL_SUMMARY_DATASET",
        "FUNDAMENTAL_REVENUE_BREAKDOWN_DATASET",
        "FUNDAMENTAL_INDUSTRY_COMPARISON_DATASET",
        "OWNERSHIP_CAPITAL_SNAPSHOT_DATASET",
        "OWNERSHIP_HOLDER_SUMMARY_SNAPSHOT_DATASET",
        "OWNERSHIP_FLOAT_HOLDER_DATASET",
        "COMPANY_EXECUTIVE_SNAPSHOT_DATASET",
        "COMPANY_EXECUTIVE_SHARE_CHANGE_DATASET",
        "CORPORATE_ACTION_DIVIDEND_DATASET",
        "CORPORATE_ACTION_REPURCHASE_DATASET",
        "MARKET_EQUITY_INTRADAY_DATASET",
        "MARKET_EQUITY_INTRADAY_5D_DATASET",
        "MARKET_INDEX_INTRADAY_DATASET",
        "MARKET_INDEX_INTRADAY_5D_DATASET",
        "MARKET_ORDERBOOK_DATASET",
        "MARKET_QUOTE_DATASET",
        "MARKET_QUOTE_SNAPSHOT_DATASET",
        "MarketKlineData",
        "MarketFundFlowDailyData",
        "MarketFundFlowIntradayData",
        "MarketFundFlowRequest",
        "MarketFundFlowSnapshotData",
        "InstrumentSectorEntry",
        "MarketInstrumentSectorSnapshotData",
        "MarketInstrumentSectorSnapshotRequest",
        "MARKET_STOCK_KEYWORD_DATASET",
        "MarketStockKeywordData",
        "MarketStockKeywordRequest",
        "StockKeywordEntry",
        "IndustryAggregate",
        "IndustryComparisonRanks",
        "IndustryComparisonValues",
        "IndustryIdentity",
        "MarketAggregate",
        "MarketIndustryComparisonData",
        "MarketIndustryComparisonRequest",
        "CompanyProfileData",
        "CompanyProfileRequest",
        "FinancialSummaryData",
        "FinancialSummaryPeriod",
        "FinancialSummaryRequest",
        "RevenueBreakdownData",
        "RevenueBreakdownRequest",
        "RevenueBreakdownRow",
        "IndustryComparisonData",
        "IndustryComparisonMetric",
        "IndustryComparisonRequest",
        "CapitalSnapshotData",
        "CapitalSnapshotRequest",
        "HolderSummarySnapshotData",
        "HolderSummarySnapshotRequest",
        "FloatHolderData",
        "FloatHolderPeriod",
        "FloatHolderRequest",
        "FloatHolderRow",
        "ExecutiveEntry",
        "ExecutiveSnapshotData",
        "ExecutiveSnapshotRequest",
        "ExecutiveShareChange",
        "ExecutiveShareChangeData",
        "ExecutiveShareChangeRequest",
        "Dividend",
        "DividendData",
        "DividendRequest",
        "Repurchase",
        "RepurchaseData",
        "RepurchaseRequest",
        "EquityIntraday5dRequest",
        "EquityIntradayData",
        "EquityIntradayRequest",
        "IndexIntraday5dRequest",
        "IndexIntradayData",
        "IndexIntradayRequest",
        "MarketOrderbookData",
        "MarketOrderbookRequest",
        "MarketQuoteData",
        "MarketQuoteSnapshotData",
        "MarketQuoteSnapshotRequest",
        "MarketQuoteUniverseRequest",
        "OrderbookLevel",
        "KlineAdjustment",
        "KlinesRequest",
        "MARKET_RANKING_DATASET",
        "MarketRankingData",
        "MarketRankingRequest",
        "RankingCriterion",
        "RankingDirection",
        "RankingMetric",
        "TRADING_CALENDAR_DATASET",
        "TradingCalendarData",
        "TradingCalendarRequest",
        "TradingCalendarService",
        "TurnoverRankingMetric",
        "VolumeRankingMetric",
        "MARKET_SENTIMENT_DATASET",
        "MarketSentimentData",
        "MarketSentimentRequest",
        "MARKET_CONSECUTIVE_LIMIT_UP_DATASET",
        "MarketConsecutiveLimitUpData",
        "MarketConsecutiveLimitUpRequest",
        "MARKET_DRAGON_TIGER_LIST_DATASET",
        "MARKET_DRAGON_TIGER_DETAIL_DATASET",
        "MarketDragonTigerListData",
        "MarketDragonTigerListRequest",
        "MarketDragonTigerDetailData",
        "MarketDragonTigerDetailRequest",
        "DragonTigerSeat",
        "MARKET_DAILY_REPLAY_DATASET",
        "MarketDailyReplayData",
        "MarketDailyReplayRequest",
        "ReplayStock",
        "ReplayTheme",
    }
    assert set(providers_api.__all__) == {
        "EastmoneyDisclosureProvider",
        "EastmoneyNewsProvider",
        "AigupiaoMarketNewsProvider",
        "BaiduFinscopeMarketNewsProvider",
        "EastmoneyMarketNewsProvider",
        "TonghuashunFinancialProvider",
        "AigupiaoDragonTigerProvider",
        "AigupiaoMarketSentimentProvider",
        "AigupiaoSeriesLimitUpProvider",
        "EastmoneyBreadthProvider",
        "EastMoneyStockKeywordProvider",
        "EastmoneyBrokenLimitPoolProvider",
        "EastmoneyLimitDownPoolProvider",
        "EastmoneyLimitUpPoolProvider",
        "EastmoneyStrongPoolProvider",
        "EastmoneyYesterdayLimitUpPoolProvider",
        "InstrumentListingProvider",
        "InstrumentProvider",
        "MarketQuoteProvider",
        "MarketRankingProvider",
        "KlinesProvider",
        "PmcTradingCalendarProvider",
        "ProviderError",
        "SzseTradingCalendarProvider",
        "TradingCalendarProvider",
        "TencentMarketProvider",
        "TencentQuoteProvider",
        "TencentFundFlowProvider",
        "TencentIndustryComparisonProvider",
        "TencentIntradayProvider",
        "TencentKlinesProvider",
        "TencentSectorProvider",
        "TencentF10Provider",
        "TencentFloatHolderProvider",
        "SohuKlinesProvider",
        "JiyangongsheReplayProvider",
    }
    assert not hasattr(datasets_api, "_ProviderInstrumentRow")
    assert not hasattr(datasets_api, "_normalize_provider_rows")
    assert not hasattr(providers_api, "_ProviderInstrumentRow")


def test_provider_error_requires_a_reason():
    source = Source(providerId="offline.fixture")
    with pytest.raises(ValueError, match="non-empty string"):
        ProviderError(source, "")
