"""Source-faithful five-slot orderbook behavior through the public API."""

from datetime import datetime, timezone

import pytest

from finchx import FinchX
from finchx.collector import CachePolicy, Collector
from finchx.contracts import DataStatus
from finchx.datasets import MARKET_ORDERBOOK_DATASET
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.errors import ProviderError
from finchx.providers.tencent import _TencentHttpResponse
from finchx.providers.tencent_quote import TencentQuoteProvider
from finchx.storage import Cache, MemoryStorage


SOURCE_TIMESTAMP = "20260928100000"
CAPTURED_AT = datetime(2026, 9, 28, 2, 0, 5, tzinfo=timezone.utc)


class _TencentOrderbookTransport:
    def __init__(self, *, ask2_size: str = "0", empty_book: bool = False, override=None):
        self.ask2_size = ask2_size
        self.empty_book = empty_book
        self.override = dict(override or {})
        self.calls: list[str] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append(url)
        symbol = url.rsplit("/q=", 1)[1]
        fields = [""] * 58
        fields[2] = symbol[2:]
        fields[3] = "10"
        fields[30] = SOURCE_TIMESTAMP
        if not self.empty_book:
            for index, value in {
                9: "10", 10: "10",      # bid 1: 10 CNY, 10 hands
                11: "0", 12: "5",       # bid 2: explicit zero price, 5 hands
                13: "", 14: "2",        # bid 3: missing price, 2 hands
                15: "9.9", 16: "",       # bid 4: price present, size missing
                17: "", 18: "",          # bid 5: both values missing
                19: "10", 20: "10",      # ask 1: 10 CNY, 10 hands
                21: "0", 22: self.ask2_size,
                23: "10.1", 24: "1",     # ask 3: 1 hand
                25: "", 26: "1",         # ask 4: missing price, 1 hand
                27: "", 28: "",          # ask 5: both values missing
            }.items():
                fields[index] = value
        for index, value in self.override.items():
            fields[index] = value
        assignment = f'v_{symbol}="{"~".join(fields)}";'
        return _TencentHttpResponse(status_code=200, text=assignment)


def _client(transport: _TencentOrderbookTransport) -> FinchX:
    provider = TencentQuoteProvider(
        transport=transport,
        clock=lambda: CAPTURED_AT,
    )
    collector = Collector(
        provider_instances={"tencent.finance.qq.quote": provider},
        cache=Cache(
            MemoryStorage(clock=lambda: CAPTURED_AT),
            clock=lambda: CAPTURED_AT,
        ),
        cache_policy={MARKET_ORDERBOOK_DATASET.name: CachePolicy(enabled=True, ttl=60)},
        clock=lambda: CAPTURED_AT,
    )
    return FinchX(collector=collector)


def test_public_orderbook_preserves_source_slots_and_cache_round_trips_them():
    transport = _TencentOrderbookTransport()
    client = _client(transport)

    first = client.market.orderbook("600519")
    cached = client.market.orderbook("600519")

    record = first.data
    assert record.status is DataStatus.LIVE
    assert record.quality.issues == []
    assert record.schema_version == "1.0"
    assert record.data == {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "kind": "equity",
            "exchange": "sse",
        },
        "bids": [
            {"level": 1, "price": "10", "size": 1000},
            {"level": 2, "price": "0", "size": 500},
            {"level": 3, "price": None, "size": 200},
            {"level": 4, "price": "9.9", "size": None},
            {"level": 5, "price": None, "size": None},
        ],
        "asks": [
            {"level": 1, "price": "10", "size": 1000},
            {"level": 2, "price": "0", "size": 0},
            {"level": 3, "price": "10.1", "size": 100},
            {"level": 4, "price": None, "size": 100},
            {"level": 5, "price": None, "size": None},
        ],
        "sourceTimestamp": "2026-09-28T10:00:00+08:00",
    }
    assert record.captured_at == CAPTURED_AT
    assert record.data["sourceTimestamp"] != record.captured_at.isoformat()
    # The fixture demonstrates a possible caller calculation, not a FinchX rule.
    assert 10 * (record.data["bids"][0]["size"] + record.data["bids"][1]["size"]) == 15000
    assert cached.cache_hit is True
    assert cached.data == first.data
    assert cached.warnings == first.warnings
    assert cached.metadata == first.metadata == {}
    assert transport.calls == ["https://qt.gtimg.cn/q=sh600519"]


@pytest.mark.parametrize(("ask2_size", "expected_size"), [("1", 100), ("", None)])
def test_orderbook_distinguishes_positive_and_missing_size(ask2_size, expected_size):
    transport = _TencentOrderbookTransport(ask2_size=ask2_size)
    result = _client(transport).market.orderbook("600519")
    ask2 = result.data.data["asks"][1]

    assert ask2 == {"level": 2, "price": "0", "size": expected_size}
    assert result.data.status is DataStatus.LIVE
    assert transport.calls == ["https://qt.gtimg.cn/q=sh600519"]


def test_orderbook_keeps_five_all_null_slots_and_marks_only_all_null_book_missing():
    transport = _TencentOrderbookTransport(empty_book=True)
    record = _client(transport).market.orderbook("600519").data

    assert record.status is DataStatus.MISSING
    assert record.quality.issues == []
    assert record.data["bids"] == [
        {"level": level, "price": None, "size": None} for level in range(1, 6)
    ]
    assert record.data["asks"] == [
        {"level": level, "price": None, "size": None} for level in range(1, 6)
    ]
    assert transport.calls == ["https://qt.gtimg.cn/q=sh600519"]


@pytest.mark.parametrize(
    ("index", "value", "error"),
    [
        (9, "-1", "book price cannot be negative"),
        (20, "-1", "book size must be a non-negative whole number of hands"),
        (20, "1.5", "book size must be a non-negative whole number of hands"),
        (9, "NaN", "book price 1 is not finite"),
    ],
)
def test_tencent_orderbook_rejects_negative_nonintegral_and_nonfinite_values(
    index, value, error
):
    transport = _TencentOrderbookTransport(override={index: value})
    provider = TencentQuoteProvider(transport=transport, clock=lambda: CAPTURED_AT)

    with pytest.raises(ProviderError, match=error):
        provider.fetch_raw_quote(
            InstrumentId(
                code="600519",
                market=Market.CN_A,
                kind=InstrumentKind.EQUITY,
                exchange=Exchange.SSE,
            )
        )
