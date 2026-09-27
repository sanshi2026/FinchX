"""Quote-snapshot support for the indices used by deviation calculations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from finchx.contracts import Source
from finchx.datasets.market_quote_snapshot import (
    MarketQuoteSnapshotRequest,
    _normalize_quote_snapshot_row,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.providers.tencent import _TencentHttpResponse
from finchx.providers.tencent_quote import TencentQuoteProvider


class _QuoteTransport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.urls.append(url)
        code = url.rsplit("/q=", 1)[1][2:]
        fields = [""] * 58
        fields[2] = code
        fields[3] = "1234.56"
        fields[4] = "1222.22"
        fields[5] = "1230.00"
        fields[6] = "10"
        fields[30] = "20260925145959"
        fields[31] = "12.34"
        fields[32] = "1.01"
        fields[33] = "1235.00"
        fields[34] = "1218.00"
        fields[36] = "10"
        fields[57] = "100"
        assignment = f'v_{url.rsplit("/q=", 1)[1]}="{"~".join(fields)}";'
        return _TencentHttpResponse(status_code=200, text=assignment)


@pytest.mark.parametrize(
    ("code", "exchange", "provider_prefix"),
    (
        ("000002", Exchange.SSE, "sh"),
        ("000688", Exchange.SSE, "sh"),
        ("399107", Exchange.SZSE, "sz"),
        ("399102", Exchange.SZSE, "sz"),
    ),
)
def test_tencent_quote_snapshot_normalizes_deviation_benchmark_indices(
    code: str, exchange: Exchange, provider_prefix: str,
) -> None:
    transport = _QuoteTransport()
    provider = TencentQuoteProvider(
        transport,
        clock=lambda: datetime(2026, 9, 25, 7, 0, tzinfo=timezone(timedelta(hours=8))),
    )
    instrument = InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
        exchange=exchange,
    )
    request = MarketQuoteSnapshotRequest(instrumentId=instrument)

    raw = provider.fetch_raw_quote(instrument)
    record = _normalize_quote_snapshot_row(request, raw, source=Source(providerId="test.tencent"))

    assert transport.urls == [f"https://qt.gtimg.cn/q={provider_prefix}{code}"]
    assert record.entity_id == instrument
    assert Decimal(record.data["price"]) == Decimal("1234.56")
    assert Decimal(record.data["previousClose"]) == Decimal("1222.22")
    assert Decimal(record.data["changeRate"]) == Decimal("0.0101")
