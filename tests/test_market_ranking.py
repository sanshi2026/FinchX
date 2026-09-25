from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finchx.contracts import DataStatus, Source
from finchx.datasets import (
    MARKET_RANKING_DATASET,
    ChangePercentRankingMetric,
    InstrumentUniverse,
    MarketQuoteData,
    MarketRankingData,
    MarketRankingRequest,
    RankingCriterion,
    RankingDirection,
    TurnoverRankingMetric,
    VolumeRankingMetric,
)
from finchx.datasets.market_ranking import (
    _ProviderRankingRow,
    _normalize_ranking_rows,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers import MarketRankingProvider


class _FakeRankingProvider:
    def __init__(self, rows=()):
        self._rows = tuple(rows)
        self._source = Source(providerId="offline.fixture")

    @property
    def source(self):
        return self._source

    def fetch_ranking(self, request):
        return self._rows


def _identity(code, exchange):
    return InstrumentId(
        code=code,
        market=Market.CN_A,
        exchange=exchange,
        kind=InstrumentKind.EQUITY,
    )


def _ranking_row(instrument_id, metric):
    values = {"instrumentId": instrument_id, "price": Decimal("10.25")}
    if metric.criterion == "turnover":
        values["amount"] = metric.value
    elif metric.criterion == "change_percent":
        values["changeRate"] = metric.value
    else:
        values["volume"] = metric.value
    return _ProviderRankingRow(data=MarketQuoteData(**values), metric=metric)


def _captured_at():
    return datetime(2026, 9, 17, 9, 30, tzinfo=timezone(timedelta(hours=8)))


@pytest.mark.parametrize(
    ("criterion", "metric"),
    [
        (RankingCriterion.TURNOVER, TurnoverRankingMetric(criterion="turnover", value=Decimal("100.25"))),
        (
            RankingCriterion.CHANGE_PERCENT,
            ChangePercentRankingMetric(criterion="change_percent", value=Decimal("0.032")),
        ),
        (RankingCriterion.VOLUME, VolumeRankingMetric(criterion="volume", value=1200)),
    ],
)
def test_ranking_value_type_is_discriminated_by_criterion(criterion, metric):
    request = MarketRankingRequest(
        universe=InstrumentUniverse.CN_A_SHARE,
        criterion=criterion,
        direction=RankingDirection.DESCENDING,
        limit=None,
    )
    provider: MarketRankingProvider = _FakeRankingProvider(
        [_ranking_row(_identity("600519", Exchange.SSE), metric)]
    )
    records = _normalize_ranking_rows(
        request,
        provider.fetch_ranking(request),
        source=provider.source,
        captured_at=_captured_at(),
    )

    assert MARKET_RANKING_DATASET.name == "market.ranking"
    assert MARKET_RANKING_DATASET.schema_version == "1.0"
    assert MARKET_RANKING_DATASET.request_type is MarketRankingRequest
    assert MARKET_RANKING_DATASET.data_type is MarketRankingData
    assert len(records) == 1
    assert records[0].entity_id == _identity("600519", Exchange.SSE)
    assert records[0].status is DataStatus.LIVE
    assert records[0].data["universe"] == "cn_a_share"
    assert records[0].data["direction"] == "descending"
    assert records[0].data["position"] == 1
    assert records[0].data["metric"]["criterion"] == criterion.value
    assert records[0].data["price"] == "10.25"
    assert records[0].data["instrumentId"] == {
        "code": "600519", "market": "cn_a", "kind": "equity", "exchange": "sse"
    }
    assert records[0].event_at is None
    assert records[0].as_of is None


def test_ranking_accepts_ascending_descending_limits_and_full_universe():
    for direction in RankingDirection:
        request = MarketRankingRequest(
            universe="cn_a_share",
            criterion="turnover",
            direction=direction,
            limit=2,
        )
        rows = [
            _ranking_row(
                _identity(code, exchange),
                TurnoverRankingMetric(criterion="turnover", value=Decimal(value)),
            )
            for code, exchange, value in (
                ("600519", Exchange.SSE, "100"),
                ("000001", Exchange.SZSE, "50"),
            )
        ]
        records = _normalize_ranking_rows(
            request,
            rows,
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )
        assert [record.data["position"] for record in records] == [1, 2]
        assert [record.data["direction"] for record in records] == [direction.value] * 2

    full_request = MarketRankingRequest(
        universe="cn_a_share",
        criterion="volume",
        direction="ascending",
        limit=None,
    )
    assert full_request.limit is None


def test_speed_is_not_a_public_ranking_criterion_in_v1():
    with pytest.raises(ValidationError):
        MarketRankingRequest(
            universe="cn_a_share",
            criterion="speed",
            direction="descending",
            limit=None,
        )


@pytest.mark.parametrize("limit", [0, -1, 1.5, "10", True])
def test_ranking_limit_must_be_positive_integer_or_none(limit):
    with pytest.raises(ValidationError):
        MarketRankingRequest(
            universe="cn_a_share",
            criterion="turnover",
            direction="descending",
            limit=limit,
        )


def test_ranking_position_must_be_positive_and_payload_must_match_request():
    with pytest.raises(ValidationError):
        MarketRankingData(
            universe="cn_a_share",
            instrumentId=_identity("600519", Exchange.SSE),
            price="10.00",
            direction="descending",
            position=0,
            metric={"criterion": "turnover", "value": "10.00"},
        )

    request = MarketRankingRequest(
        universe="cn_a_share",
        criterion="volume",
        direction="descending",
        limit=None,
    )
    wrong_metric = _ranking_row(
        _identity("600519", Exchange.SSE),
        TurnoverRankingMetric(criterion="turnover", value=Decimal("10.00")),
    )
    with pytest.raises(ValueError, match="does not match the requested criterion"):
        _normalize_ranking_rows(
            request,
            [wrong_metric],
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )

    inconsistent_metric = _ProviderRankingRow(
        data=MarketQuoteData(
            instrumentId=_identity("600519", Exchange.SSE),
            price="10.00",
            amount="9.00",
        ),
        metric=TurnoverRankingMetric(criterion="turnover", value=Decimal("10.00")),
    )
    turnover_request = MarketRankingRequest(
        universe="cn_a_share",
        criterion="turnover",
        direction="descending",
        limit=None,
    )
    with pytest.raises(ValueError, match="does not match the quote field"):
        _normalize_ranking_rows(
            turnover_request,
            [inconsistent_metric],
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )


@pytest.mark.parametrize(
    ("criterion", "value"),
    [
        ("turnover", 100),
        ("turnover", "not-decimal"),
        ("change_percent", 3),
        ("volume", "100"),
        ("volume", 1.5),
    ],
)
def test_ranking_rejects_mismatched_or_invalid_metric_values(criterion, value):
    with pytest.raises(ValidationError):
        MarketRankingData(
            universe="cn_a_share",
            instrumentId=_identity("600519", Exchange.SSE),
            price="10.00",
            direction="descending",
            position=1,
            metric={"criterion": criterion, "value": value},
        )


def test_ranking_rejects_rows_over_limit_and_includes_full_quote_fields():
    request = MarketRankingRequest(
        universe="cn_a_share",
        criterion="change_percent",
        direction="descending",
        limit=1,
    )
    rows = [
        _ranking_row(
            _identity(code, exchange),
            ChangePercentRankingMetric(criterion="change_percent", value=Decimal("0.01")),
        )
        for code, exchange in (("600519", Exchange.SSE), ("000001", Exchange.SZSE))
    ]
    with pytest.raises(ValueError, match="more ranking rows"):
        _normalize_ranking_rows(
            request,
            rows,
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )

    data = MarketRankingData(
        universe="cn_a_share",
        instrumentId=_identity("600519", Exchange.SSE),
        price="10.00",
        direction="descending",
        position=1,
        metric={"criterion": "change_percent", "value": "0.01"},
    )
    ranking_wire = data.model_dump(mode="json", by_alias=True)
    quote_fields = set(MarketQuoteData.model_json_schema(by_alias=True)["properties"])
    assert quote_fields.issubset(ranking_wire)
    assert ranking_wire["price"] == "10.00"
