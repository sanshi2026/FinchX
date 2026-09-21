from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finchx.contracts import DataStatus, QualityIssueKind, Source
from finchx.datasets import (
    MARKET_QUOTE_DATASET,
    InstrumentUniverse,
    MarketQuoteData,
    MarketQuoteUniverseRequest,
)
from finchx.datasets.market_quote import _ProviderQuoteRow, _normalize_quote_rows
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers import MarketQuoteProvider


class _FakeQuoteProvider:
    def __init__(self, rows=()):
        self._rows = tuple(rows)
        self._source = Source(providerId="offline.fixture")

    @property
    def source(self):
        return self._source

    def fetch_quotes(self, request):
        assert request.universe is InstrumentUniverse.CN_A_SHARE
        return self._rows


def _identity(code="600519", exchange=Exchange.SSE):
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        exchange=exchange,
        kind=InstrumentKind.EQUITY,
    )


def _captured_at():
    return datetime(2026, 9, 17, 9, 30, tzinfo=timezone(timedelta(hours=8)))


def test_market_quote_dataset_is_a_universe_snapshot_with_one_record_per_instrument():
    rows = (
        _ProviderQuoteRow(
            MarketQuoteData(
                instrumentId=_identity(),
                name="贵州茅台",
                price=Decimal("1475.20"),
                priceChange=Decimal("-12.30"),
                changeRate=Decimal("-0.0083"),
                changeRate5d=Decimal("0.1234"),
                changeRate10d=Decimal("-0.055"),
                changeRate20d=Decimal("0.2"),
                changeRate60d=Decimal("-0.3"),
                changeRate52w=Decimal("1.25"),
                changeRateYtd=Decimal("0.05"),
                amplitude=Decimal("0.0825"),
                volumeRatio=Decimal("2.35"),
                volume=1200,
                amount=Decimal("123456789.25"),
                turnoverRate=Decimal("0.0042"),
                marketCap=Decimal("1850000000000"),
                floatMarketCap=Decimal("1800000000000"),
                peTtm=Decimal("-5.25"),
                mainNetInflow=Decimal("10000"),
                mainInflow=Decimal("20000"),
                mainOutflow=Decimal("10000"),
                mainInflow5d=Decimal("30000"),
                mainOutflow5d=Decimal("25000"),
            ),
            source_record_id="quote-600519",
        ),
        _ProviderQuoteRow(
            MarketQuoteData(
                instrumentId=_identity("000001", Exchange.SZSE),
                name="平安银行",
                price=Decimal("10.20"),
            )
        ),
    )
    provider: MarketQuoteProvider = _FakeQuoteProvider(rows)
    request = MarketQuoteUniverseRequest(universe=InstrumentUniverse.CN_A_SHARE)
    records = _normalize_quote_rows(
        request,
        provider.fetch_quotes(request),
        source=provider.source,
        captured_at=_captured_at(),
    )

    assert MARKET_QUOTE_DATASET.name == "market.quote"
    assert MARKET_QUOTE_DATASET.schema_version == "1.0"
    assert MARKET_QUOTE_DATASET.request_type is MarketQuoteUniverseRequest
    assert MARKET_QUOTE_DATASET.data_type is MarketQuoteData
    assert len(records) == 2
    assert all(record.dataset == "market.quote" for record in records)
    assert all(record.captured_at == _captured_at() for record in records)
    assert all(record.event_at is None for record in records)
    assert all(record.published_at is None for record in records)
    assert all(record.updated_at is None for record in records)
    assert all(record.as_of is None for record in records)
    assert all(record.status is DataStatus.LIVE for record in records)
    assert records[0].data["priceChange"] == "-12.30"
    assert records[0].data["changeRate"] == "-0.0083"
    assert records[0].data["changeRate5d"] == "0.1234"
    assert records[0].data["changeRate10d"] == "-0.055"
    assert records[0].data["changeRate20d"] == "0.2"
    assert records[0].data["changeRate60d"] == "-0.3"
    assert records[0].data["changeRate52w"] == "1.25"
    assert records[0].data["changeRateYtd"] == "0.05"
    assert records[0].data["amplitude"] == "0.0825"
    assert records[0].data["volumeRatio"] == "2.35"
    assert records[0].data["peTtm"] == "-5.25"
    assert "priceToBook" not in records[0].data
    assert records[0].data["mainNetInflow"] == "10000"
    assert records[0].data["mainInflow"] == "20000"
    assert records[0].data["mainOutflow"] == "10000"
    assert records[0].data["mainInflow5d"] == "30000"
    assert records[0].data["mainOutflow5d"] == "25000"
    assert records[0].source.source_record_id == "quote-600519"
    assert records[0].quality.issues == []
    assert records[1].data["name"] == "平安银行"
    assert records[1].data["volume"] is None
    assert records[1].quality.issues[0].kind is QualityIssueKind.PARTIAL


def test_quote_none_zero_negative_and_decimal_values_remain_distinct():
    quote = MarketQuoteData(
        instrumentId=_identity(),
        price=Decimal("0"),
        priceChange=Decimal("0"),
        changeRate=Decimal("0"),
        changeRate5d=Decimal("0"),
        changeRate10d=Decimal("0"),
        changeRate20d=Decimal("0"),
        changeRate60d=Decimal("0"),
        changeRate52w=Decimal("0"),
        changeRateYtd=Decimal("0"),
        amplitude=Decimal("0"),
        volumeRatio=Decimal("0"),
        volume=0,
        amount=Decimal("0"),
        turnoverRate=Decimal("0"),
        marketCap=Decimal("0"),
        floatMarketCap=Decimal("0"),
        peTtm=Decimal("-2.5"),
        mainNetInflow=Decimal("0"),
    )
    dumped = quote.model_dump(mode="json", by_alias=True)

    assert quote.name is None
    assert quote.price_change == Decimal("0")
    assert quote.change_rate == Decimal("0")
    assert quote.volume == 0
    assert dumped["price"] == "0"
    assert dumped["priceChange"] == "0"
    assert dumped["amount"] == "0"
    assert dumped["volume"] == 0
    assert dumped["changeRate5d"] == "0"
    assert dumped["changeRate10d"] == "0"
    assert dumped["changeRate20d"] == "0"
    assert dumped["changeRate60d"] == "0"
    assert dumped["changeRate52w"] == "0"
    assert dumped["changeRateYtd"] == "0"
    assert dumped["amplitude"] == "0"
    assert dumped["volumeRatio"] == "0"
    assert dumped["peTtm"] == "-2.5"
    assert "priceToBook" not in dumped
    assert dumped["mainNetInflow"] == "0"


@pytest.mark.parametrize("bad_price", [1.2, 12, "1e2", "01.2", "NaN"])
def test_quote_rejects_noncanonical_or_non_decimal_price(bad_price):
    with pytest.raises(ValidationError):
        MarketQuoteData(instrumentId=_identity(), price=bad_price)


@pytest.mark.parametrize("bad_shares", [1.5, "100", True, -1])
def test_quote_requires_nonnegative_strict_integer_share_counts(bad_shares):
    with pytest.raises(ValidationError):
        MarketQuoteData(instrumentId=_identity(), price="10.00", volume=bad_shares)


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("-0")])
def test_quote_rejects_negative_volume_ratio(value):
    with pytest.raises(ValidationError, match="volume ratio must not be negative"):
        MarketQuoteData(
            instrumentId=_identity(),
            price="10.00",
            volumeRatio=value,
        )


def test_quote_requires_a_complete_instrument_identity_and_rejects_provider_fields():
    with pytest.raises(ValidationError):
        MarketQuoteData(instrumentId={"code": "600519"}, price="10.00")
    with pytest.raises(ValidationError):
        MarketQuoteData(
            instrumentId=_identity(),
            price="10.00",
            tencentFields={"pn": "1.2"},
        )


def test_quote_normalizer_rejects_wrong_universe_and_duplicate_identities():
    quote = MarketQuoteData(instrumentId=_identity(), price="10.00")
    source = Source(providerId="offline.fixture")
    with pytest.raises(ValueError, match="non-A-share-equity"):
        _normalize_quote_rows(
            MarketQuoteUniverseRequest(universe="cn_a_share"),
            (_ProviderQuoteRow(MarketQuoteData(
                instrumentId=InstrumentId(
                    code="000001",
                    market=Market.CN_A,
                    exchange=Exchange.SSE,
                    kind=InstrumentKind.INDEX,
                ),
                price="10.00",
            )),),
            source=source,
            captured_at=_captured_at(),
        )
    with pytest.raises(ValueError, match="duplicate identity"):
        _normalize_quote_rows(
            MarketQuoteUniverseRequest(universe="cn_a_share"),
            (_ProviderQuoteRow(quote), _ProviderQuoteRow(quote)),
            source=source,
            captured_at=_captured_at(),
        )
