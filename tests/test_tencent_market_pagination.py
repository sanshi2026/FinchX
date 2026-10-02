from datetime import datetime, timezone
from decimal import Decimal

import pytest

from finchx import FinchX
from finchx.collector import CachePolicy, Collector
from finchx.contracts import Source
from finchx.datasets import INSTRUMENT_DATASET, InstrumentRequest
from finchx.datasets.market_quote import MARKET_QUOTE_DATASET
from finchx.datasets.market_ranking import (
    MARKET_RANKING_DATASET,
    MarketRankingRequest,
    RankingCriterion,
    RankingDirection,
    _ProviderRankingResponse,
    _normalize_ranking_rows,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError
from finchx.providers.tencent import (
    TencentMarketProvider,
    _TencentHttpResponse,
    _TencentMarketRow,
)
from finchx.storage import Cache, MemoryStorage


def _market_row(code: str, page_offset: int, row_index: int) -> _TencentMarketRow:
    return _TencentMarketRow(
        instrument_id=InstrumentId(
            code=code,
            market=Market.CN_A,
            kind=InstrumentKind.EQUITY,
            exchange=Exchange.SZSE,
        ),
        source_code=f"sz{code}",
        stock_type="GP-A",
        name=f"Stock {code}",
        price=Decimal("10.00"),
        price_change=Decimal("0.10"),
        change_rate=Decimal("0.01"),
        volume=100,
        amount=Decimal("1000"),
        turnover_rate=None,
        market_cap=None,
        float_market_cap=None,
        pe_ttm=None,
        change_rate_5d=None,
        change_rate_10d=None,
        change_rate_20d=None,
        change_rate_60d=None,
        change_rate_52w=None,
        change_rate_ytd=None,
        amplitude=None,
        volume_ratio=None,
        main_net_inflow=None,
        main_inflow=None,
        main_outflow=None,
        main_inflow_5d=None,
        main_outflow_5d=None,
        speed=None,
        captured_at=datetime(2026, 9, 28, 1, 20, tzinfo=timezone.utc),
        row_context=f"offset={page_offset}, row={row_index}",
        ranking_position=page_offset + row_index + 1,
    )


def _request(
    limit: int | None,
    direction: RankingDirection = RankingDirection.DESCENDING,
) -> MarketRankingRequest:
    return MarketRankingRequest(
        universe="cn_a_share",
        criterion=RankingCriterion.CHANGE_PERCENT,
        direction=direction,
        limit=limit,
    )


@pytest.mark.parametrize(
    ("direction", "expected_direct"),
    [
        (RankingDirection.DESCENDING, "down"),
        (RankingDirection.ASCENDING, "up"),
    ],
)
def test_live_ranking_skips_cross_page_overlap_with_partial_coverage(
    monkeypatch, direction, expected_direct
):
    provider = TencentMarketProvider()
    page_ranges = ((0, 1), (100, 100), (200, 199), (300, 298), (400, 397))
    pages = {
        offset: tuple(
            _market_row(f"{code:06d}", offset, row_index)
            for row_index, code in enumerate(range(first_code, first_code + 100))
        )
        for offset, first_code in page_ranges
    }
    offsets = []

    def fetch_page(*, sort_type, direct, offset, count):
        assert sort_type == "priceRatio"
        assert direct == expected_direct
        assert count == 100
        offsets.append(offset)
        try:
            return pages[offset], 1000
        except KeyError as error:
            raise AssertionError(f"unexpected source page at offset={offset}") from error

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    response = provider.fetch_ranking(_request(500, direction))

    assert isinstance(response, _ProviderRankingResponse)
    assert offsets == [0, 100, 200, 300, 400]
    assert len(response) == 496
    assert response.metadata == {
        "coverage_status": "partial",
        "requested_count": 500,
        "source_row_count": 500,
        "unique_count": 496,
        "source_total": 1000,
        "duplicate_rows_skipped": 4,
    }
    assert len(response.warnings) == 1
    assert "returned 496 unique rows out of 500 requested after reading 500 source rows" in response.warnings[0]
    records = _normalize_ranking_rows(
        _request(500, direction),
        response,
        source=Source(providerId="tencent.finance.qq.market"),
        captured_at=datetime(2026, 9, 28, 1, 21, tzinfo=timezone.utc),
    )
    assert len(records) == 496
    assert records[-1].data["position"] == 500


@pytest.mark.parametrize(
    ("row_count", "total", "limit", "error"),
    [
        (0, 10, 5, "pagination ended early"),
        (1, 10, 10, "short page before total"),
        (3, 10, 2, "returned 3 rows for count=2"),
    ],
)
def test_ranking_still_rejects_empty_short_and_oversized_pages(
    monkeypatch, row_count, total, limit, error
):
    provider = TencentMarketProvider()
    page = tuple(
        _market_row(f"{code:06d}", 0, row_index)
        for row_index, code in enumerate(range(1, row_count + 1))
    )
    monkeypatch.setattr(provider, "_fetch_page", lambda **kwargs: (page, total))

    with pytest.raises(ProviderError, match=error):
        provider.fetch_ranking(_request(limit))


def test_ranking_still_rejects_total_drift(monkeypatch):
    provider = TencentMarketProvider()
    first_page = tuple(_market_row(f"{code:06d}", 0, code - 1) for code in range(1, 101))
    second_page = tuple(_market_row(f"{code:06d}", 100, code - 100) for code in range(101, 151))

    def fetch_page(*, offset, **kwargs):
        return (first_page, 150) if offset == 0 else (second_page, 151)

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    with pytest.raises(ProviderError, match="pagination total drift at offset=100"):
        provider.fetch_ranking(_request(150))


@pytest.mark.parametrize(
    ("response_text", "error"),
    [
        ('{"data":{"rank_list":[],"total":10,"offset":1}}', "response offset mismatch"),
        ('{"data":{"rank_list":[[]],"total":1,"offset":0}}', "field row must be an object"),
    ],
)
def test_ranking_still_rejects_offset_mismatch_and_invalid_row_format(response_text, error):
    class StaticTransport:
        def get(self, *args, **kwargs):
            return _TencentHttpResponse(status_code=200, text=response_text)

    provider = TencentMarketProvider(transport=StaticTransport())

    with pytest.raises(ProviderError, match=error):
        provider.fetch_ranking(_request(1))


def test_live_ranking_still_rejects_duplicate_identity_within_one_page(monkeypatch):
    provider = TencentMarketProvider()
    duplicate = _market_row("000001", 0, 0)
    monkeypatch.setattr(
        provider,
        "_fetch_page",
        lambda **kwargs: ((duplicate, duplicate), 10),
    )

    with pytest.raises(ProviderError, match="duplicate instrument id within Tencent page"):
        provider.fetch_ranking(_request(2))


def test_public_quote_preserves_partial_pagination_metadata_through_cache(monkeypatch):
    provider = TencentMarketProvider()
    first_page = tuple(_market_row(f"{code:06d}", 0, code - 1) for code in range(1, 101))
    second_page = (_market_row("000100", 100, 0),)
    page_calls = []

    def fetch_page(*, offset, count, **kwargs):
        page_calls.append((offset, count))
        return (first_page if offset == 0 else second_page), 101

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    captured_at = datetime(2026, 9, 28, 1, 20, tzinfo=timezone.utc)
    collector = Collector(
        provider_instances={"tencent.finance.qq.market": provider},
        cache=Cache(MemoryStorage(clock=lambda: captured_at), clock=lambda: captured_at),
        cache_policy={MARKET_QUOTE_DATASET.name: CachePolicy(enabled=True, ttl=60)},
        clock=lambda: captured_at,
    )
    client = FinchX(collector=collector)

    first = client.market.quote()
    cached = client.market.quote()

    assert len(first.data) == 100
    assert first.metadata == {
        "coverage_status": "partial",
        "requested_count": 101,
        "source_row_count": 101,
        "unique_count": 100,
        "source_total": 101,
        "duplicate_rows_skipped": 1,
        "returned_count": 100,
    }
    assert len(first.warnings) == 1
    assert "not a consistent point-in-time quote listing" in first.warnings[0]
    assert cached.cache_hit is True
    assert cached.metadata == first.metadata
    assert cached.warnings == first.warnings
    assert page_calls == [(0, 100), (100, 1)]


def test_public_instrument_exact_lookup_preserves_listing_overlap_metadata(monkeypatch):
    provider = TencentMarketProvider()
    first_page = tuple(_market_row(f"{code:06d}", 0, code - 1) for code in range(1, 101))
    second_page = (_market_row("000100", 100, 0),)
    page_calls = []

    def fetch_page(*, offset, count, **kwargs):
        page_calls.append((offset, count))
        return (first_page if offset == 0 else second_page), 101

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    captured_at = datetime(2026, 9, 28, 1, 20, tzinfo=timezone.utc)
    collector = Collector(
        provider_instances={"tencent.finance.qq.market": provider},
        cache=Cache(MemoryStorage(clock=lambda: captured_at), clock=lambda: captured_at),
        cache_policy={INSTRUMENT_DATASET.name: CachePolicy(enabled=True, ttl=60)},
        clock=lambda: captured_at,
    )
    client = FinchX(collector=collector)
    request = InstrumentRequest(instrumentId=first_page[0].instrument_id)

    first = client.fetch(INSTRUMENT_DATASET, request=request)
    cached = client.fetch(INSTRUMENT_DATASET, request=request)

    assert len(first.data) == 1
    assert first.data[0].data["name"] == "Stock 000001"
    assert first.metadata == {
        "coverage_status": "partial",
        "requested_count": 101,
        "source_row_count": 101,
        "unique_count": 100,
        "source_total": 101,
        "duplicate_rows_skipped": 1,
        "returned_count": 1,
    }
    assert len(first.warnings) == 1
    assert "not a consistent point-in-time instrument listing" in first.warnings[0]
    assert cached.cache_hit is True
    assert cached.metadata == first.metadata
    assert cached.warnings == first.warnings
    assert page_calls == [(0, 100), (100, 1)]


def test_public_client_preserves_partial_metadata_and_warnings_through_cache(monkeypatch):
    provider = TencentMarketProvider()
    calls = []
    pages = {
        0: tuple(_market_row(f"{code:06d}", 0, code - 1) for code in range(1, 101)),
        100: tuple(_market_row(f"{code:06d}", 100, code - 100) for code in range(100, 150)),
    }

    def fetch_page(*, sort_type, direct, offset, count):
        calls.append((offset, count))
        assert sort_type == "priceRatio"
        assert direct == "down"
        return pages[offset], 150

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    captured_at = datetime(2026, 9, 28, 1, 20, tzinfo=timezone.utc)
    collector = Collector(
        provider_instances={"tencent.finance.qq.market": provider},
        cache=Cache(MemoryStorage(clock=lambda: captured_at), clock=lambda: captured_at),
        cache_policy={MARKET_RANKING_DATASET.name: CachePolicy(enabled=True, ttl=60)},
        clock=lambda: captured_at,
    )
    client = FinchX(collector=collector)

    first = client.market.ranking("zdf", "desc", 500)
    cached = client.market.ranking("zdf", "desc", 500)

    positions = [record.data["position"] for record in first.data]
    assert calls == [(0, 100), (100, 50)]
    assert len(first.data) == 149
    assert positions[-1] == 150
    assert 101 not in positions
    assert first.metadata == {
        "coverage_status": "partial",
        "requested_count": 500,
        "source_row_count": 150,
        "unique_count": 149,
        "source_total": 150,
        "duplicate_rows_skipped": 1,
        "returned_count": 149,
    }
    assert len(first.warnings) == 1
    assert "not a consistent point-in-time ranking" in first.warnings[0]
    assert cached.cache_hit is True
    assert cached.metadata == first.metadata
    assert cached.warnings == first.warnings
    assert cached.captured_at == first.captured_at
    assert calls == [(0, 100), (100, 50)]


def test_unlimited_ranking_reads_through_source_total_and_reports_overlap(monkeypatch):
    provider = TencentMarketProvider()
    offsets = []
    pages = {
        0: tuple(_market_row(f"{code:06d}", 0, code - 1) for code in range(1, 101)),
        100: (_market_row("000100", 100, 0),),
    }

    def fetch_page(*, offset, count, **kwargs):
        offsets.append((offset, count))
        return pages[offset], 101

    monkeypatch.setattr(provider, "_fetch_page", fetch_page)
    response = provider.fetch_ranking(_request(None))

    assert isinstance(response, _ProviderRankingResponse)
    assert offsets == [(0, 100), (100, 1)]
    assert len(response) == 100
    assert response[-1].position == 100
    assert response.metadata == {
        "coverage_status": "partial",
        "requested_count": 101,
        "source_row_count": 101,
        "unique_count": 100,
        "source_total": 101,
        "duplicate_rows_skipped": 1,
    }
