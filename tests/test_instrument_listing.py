from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from finchx.contracts import Source
from finchx.datasets import (
    INSTRUMENT_DATASET,
    InstrumentData,
    InstrumentRequest,
    InstrumentUniverse,
    InstrumentUniverseRequest,
)
from finchx.datasets.instrument import (
    _ProviderInstrumentRow,
    _normalize_listing_provider_rows,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market, format_symbol
from finchx.providers import InstrumentListingProvider


class _FakeListingProvider:
    def __init__(self, rows=()):
        self._rows = tuple(rows)
        self._source = Source(providerId="offline.fixture")

    @property
    def source(self):
        return self._source

    def list_instruments(self, request):
        assert request.universe is InstrumentUniverse.CN_A_SHARE
        return self._rows


def _captured_at():
    return datetime(2026, 9, 17, 9, 30, tzinfo=timezone(timedelta(hours=8)))


def _row(code, exchange, name):
    return _ProviderInstrumentRow(
        code=code,
        market="cn_a",
        exchange=exchange,
        kind="equity",
        name=name,
        source_record_id=f"fixture-{code}",
    )


def test_listing_returns_individual_instrument_records_for_all_declared_exchanges():
    rows = (
        _row("600519", "sse", "贵州茅台"),
        _row("000001", "szse", "平安银行"),
        _row("830799", "bse", "样例北交所"),
    )
    provider: InstrumentListingProvider = _FakeListingProvider(rows)
    request = InstrumentUniverseRequest(universe=InstrumentUniverse.CN_A_SHARE)

    records = _normalize_listing_provider_rows(
        request,
        provider.list_instruments(request),
        source=provider.source,
        captured_at=_captured_at(),
    )

    assert len(records) == 3
    assert [record.dataset for record in records] == ["instrument"] * 3
    assert [record.schema_version for record in records] == ["1.0"] * 3
    assert [record.entity_id.exchange for record in records] == [
        Exchange.SSE,
        Exchange.SZSE,
        Exchange.BSE,
    ]
    assert all(record.entity_id.market is Market.CN_A for record in records)
    assert all(record.entity_id.kind is InstrumentKind.EQUITY for record in records)
    assert all(record.captured_at == _captured_at() for record in records)
    assert all(record.event_at is None for record in records)
    assert all(record.as_of is None for record in records)
    assert [InstrumentData.model_validate(record.data).name for record in records] == [
        "贵州茅台",
        "平安银行",
        "样例北交所",
    ]
    assert records[0].record_id == format_symbol(records[0].entity_id)
    assert records[0].source.source_record_id == "fixture-600519"


def test_empty_listing_is_a_successful_empty_tuple():
    provider: InstrumentListingProvider = _FakeListingProvider()
    request = InstrumentUniverseRequest(universe="cn_a_share")

    assert _normalize_listing_provider_rows(
        request,
        provider.list_instruments(request),
        source=provider.source,
        captured_at=_captured_at(),
    ) == ()


def test_listing_rejects_duplicates_and_non_equity_identities():
    duplicate = _row("600519", "sse", "贵州茅台")
    with pytest.raises(ValueError, match="duplicate identity"):
        _normalize_listing_provider_rows(
            InstrumentUniverseRequest(universe="cn_a_share"),
            (duplicate, duplicate),
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )

    index = _ProviderInstrumentRow(
        code="000001",
        market="cn_a",
        exchange="sse",
        kind="index",
        name="指数",
    )
    with pytest.raises(ValueError, match="non-A-share-equity"):
        _normalize_listing_provider_rows(
            InstrumentUniverseRequest(universe="cn_a_share"),
            (index,),
            source=Source(providerId="offline.fixture"),
            captured_at=_captured_at(),
        )


def test_universe_request_is_explicit_and_existing_single_lookup_definition_is_unchanged():
    assert InstrumentUniverseRequest(universe="cn_a_share").universe is InstrumentUniverse.CN_A_SHARE
    with pytest.raises(ValidationError):
        InstrumentUniverseRequest(universe="all_markets")

    assert INSTRUMENT_DATASET.name == "instrument"
    assert INSTRUMENT_DATASET.schema_version == "1.0"
    assert INSTRUMENT_DATASET.request_type is InstrumentRequest
    assert INSTRUMENT_DATASET.data_type is InstrumentData
    assert InstrumentRequest(
        instrumentId=InstrumentId(
            code="600519",
            market=Market.CN_A,
            exchange=Exchange.SSE,
            kind=InstrumentKind.EQUITY,
        )
    ).instrument_id.code == "600519"
