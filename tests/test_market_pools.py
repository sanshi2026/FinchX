from datetime import date, datetime, timezone
import json
from typing import Any

import pytest

from finchx.contracts import StandardRecord
from finchx.datasets import (
    MarketBrokenLimitPoolRequest,
    MarketLimitDownPoolRequest,
    MarketLimitUpPoolRequest,
    MarketStrongPoolRequest,
    MarketYesterdayLimitUpPoolRequest,
)
from finchx.datasets.market_broken_limit_pool import normalize_market_broken_limit_pool
from finchx.datasets.market_limit_down_pool import normalize_market_limit_down_pool
from finchx.datasets.market_limit_up_pool import normalize_market_limit_up_pool
from finchx.datasets.market_strong_pool import normalize_market_strong_pool
from finchx.datasets.market_yesterday_limit_up_pool import normalize_market_yesterday_limit_up_pool
from finchx.providers import (
    EastmoneyBrokenLimitPoolProvider,
    EastmoneyLimitDownPoolProvider,
    EastmoneyLimitUpPoolProvider,
    EastmoneyStrongPoolProvider,
    EastmoneyYesterdayLimitUpPoolProvider,
)
from finchx.providers.errors import ProviderError


OBSERVED_DATE = date(2026, 9, 22)
CAPTURED_AT = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


class _Response:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text


class _Transport:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.calls: list[dict[str, Any]] = []

    def get(self, url, *, params, headers, timeout_seconds):
        self.calls.append({"url": url, "params": dict(params)})
        payload = {"rc": 0, "data": {"qdate": "20260922", "tc": 1, "pool": [self.row]}}
        return _Response(f"finchxEastmoney({json.dumps(payload)})")


def _provider_case():
    return [
        pytest.param(
            EastmoneyLimitUpPoolProvider,
            MarketLimitUpPoolRequest,
            normalize_market_limit_up_pool,
            "fetch_raw_limit_up_pool",
            {
                "c": "600519", "m": 1, "n": "贵州茅台", "p": "1500000", "zdp": "1.2",
                "amount": "1000000", "ltsz": "2000000", "tshare": "3000000", "hs": "2.3",
                "lbc": 2, "fbt": 93000, "lbt": 140000, "fund": "100", "zbc": 0,
                "hybk": "白酒", "zttj": {"days": 5, "ct": 2},
            },
            id="limit-up",
        ),
        pytest.param(
            EastmoneyLimitDownPoolProvider,
            MarketLimitDownPoolRequest,
            normalize_market_limit_down_pool,
            "fetch_raw_limit_down_pool",
            {
                "c": "000001", "m": 0, "n": "平安银行", "p": "10000", "zdp": "-9.8",
                "amount": "1000000", "ltsz": "2000000", "tshare": "3000000", "pe": "8.0",
                "hs": "2.3", "fund": "100", "lbt": 140000, "fba": "100", "days": 1,
                "oc": 2, "hybk": "银行",
            },
            id="limit-down",
        ),
        pytest.param(
            EastmoneyYesterdayLimitUpPoolProvider,
            MarketYesterdayLimitUpPoolRequest,
            normalize_market_yesterday_limit_up_pool,
            "fetch_raw_yesterday_limit_up_pool",
            {
                "c": "600519", "m": 1, "n": "贵州茅台", "p": "1500000", "ztp": "1650000",
                "zdp": "1.2", "amount": "1000000", "ltsz": "2000000", "tshare": "3000000",
                "hs": "2.3", "zf": "3.4", "zs": "1.2", "yfbt": 93000, "ylbc": 2,
                "hybk": "白酒", "zttj": {"days": 5, "ct": 2},
            },
            id="yesterday-limit-up",
        ),
        pytest.param(
            EastmoneyStrongPoolProvider,
            MarketStrongPoolRequest,
            normalize_market_strong_pool,
            "fetch_raw_strong_pool",
            {
                "c": "600519", "m": 1, "n": "贵州茅台", "p": "1500000", "ztp": "1650000",
                "ztf": "1", "zdp": "1.2", "amount": "1000000", "ltsz": "2000000",
                "tshare": "3000000", "hs": "2.3", "nh": 1, "cc": 1, "lb": "2.3",
                "zs": "1.2", "zttj": {"days": 5, "ct": 2}, "hybk": "白酒",
            },
            id="strong",
        ),
        pytest.param(
            EastmoneyBrokenLimitPoolProvider,
            MarketBrokenLimitPoolRequest,
            normalize_market_broken_limit_pool,
            "fetch_raw_broken_limit_pool",
            {
                "c": "600519", "m": 1, "n": "贵州茅台", "p": "1500000", "ztp": "1650000",
                "zdp": "1.2", "amount": "1000000", "ltsz": "2000000", "tshare": "3000000",
                "hs": "2.3", "fbt": 93000, "zbc": 1, "zf": "3.4", "zs": "1.2",
                "zttj": {"days": 5, "ct": 2}, "hybk": "白酒",
            },
            id="broken-limit",
        ),
    ]


@pytest.mark.parametrize(
    "provider_type, request_type, normalizer, fetch_method, row",
    _provider_case(),
)
def test_pool_providers_fetch_latest_snapshot_and_record_source_qdate(
    provider_type,
    request_type,
    normalizer,
    fetch_method,
    row,
):
    transport = _Transport(row)
    provider = provider_type(transport=transport, clock=lambda: CAPTURED_AT)
    request = request_type()

    raw_rows = getattr(provider, fetch_method)(request)
    records = normalizer(request, raw_rows, source=provider.source)

    assert transport.calls
    assert "date" not in transport.calls[0]["params"]
    assert raw_rows[0].trade_date == OBSERVED_DATE
    assert isinstance(records[0], StandardRecord)
    assert records[0].data["tradeDate"] == OBSERVED_DATE.isoformat()


@pytest.mark.parametrize(
    "provider_type, request_type, fetch_method",
    [
        (EastmoneyLimitUpPoolProvider, MarketLimitUpPoolRequest, "fetch_raw_limit_up_pool"),
        (EastmoneyLimitDownPoolProvider, MarketLimitDownPoolRequest, "fetch_raw_limit_down_pool"),
        (EastmoneyYesterdayLimitUpPoolProvider, MarketYesterdayLimitUpPoolRequest, "fetch_raw_yesterday_limit_up_pool"),
        (EastmoneyStrongPoolProvider, MarketStrongPoolRequest, "fetch_raw_strong_pool"),
        (EastmoneyBrokenLimitPoolProvider, MarketBrokenLimitPoolRequest, "fetch_raw_broken_limit_pool"),
    ],
)
def test_legacy_trade_date_is_not_silently_treated_as_a_historical_query(
    provider_type,
    request_type,
    fetch_method,
):
    provider = provider_type(transport=_Transport({}), clock=lambda: CAPTURED_AT)

    with pytest.raises(ProviderError, match="latest snapshot only.*tradeDate"):
        getattr(provider, fetch_method)(request_type(tradeDate=date(2020, 1, 2)))
