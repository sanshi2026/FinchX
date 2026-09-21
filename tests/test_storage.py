from datetime import date, datetime, timezone
import inspect

import pytest

from finchx.contracts import (
    Provenance,
    ProvenanceClass,
    Source,
    StandardRecord,
)
from finchx.datasets import (
    FINANCIAL_STATEMENT_DATASET,
    MARKET_QUOTE_DATASET,
    NEWS_DOCUMENT_DATASET,
    FinancialStatementData,
    NewsDocumentData,
)
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market
from finchx.storage import (
    InvalidStorageKey,
    InvalidStoredObject,
    MemoryStorage,
    Storage,
    StorageKey,
)


INSTRUMENT = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
CAPTURED_AT = datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc)


def test_storage_key_is_deterministic_and_canonicalizes_mapping_order():
    left = StorageKey.from_dataset(
        MARKET_QUOTE_DATASET,
        {"instrument": INSTRUMENT, "tradeDate": date(2026, 9, 18)},
    )
    right = StorageKey(
        "market.quote",
        "1.0",
        {"tradeDate": date(2026, 9, 18), "instrument": INSTRUMENT},
    )

    assert left == right
    assert hash(left) == hash(right)
    assert left.serialized == str(right)
    assert left.namespace == "market.quote/1.0"


def test_storage_key_separates_dataset_version_and_logical_identity():
    market_key = StorageKey("market.quote", "1.0", {"instrument": INSTRUMENT})
    financial_key = StorageKey("financial.statement", "1.0", {"instrument": INSTRUMENT})
    newer_version_key = StorageKey("market.quote", "2.0", {"instrument": INSTRUMENT})
    another_period_key = StorageKey(
        "market.quote", "1.0", {"instrument": INSTRUMENT, "tradeDate": date(2026, 9, 19)}
    )

    assert len({market_key, financial_key, newer_version_key, another_period_key}) == 4
    assert market_key.dataset_version == "1.0"


def test_provider_is_not_part_of_logical_identity_and_source_metadata_is_retained():
    key = StorageKey.from_dataset(NEWS_DOCUMENT_DATASET, {"documentId": "news-001"})
    source = Source(providerId="eastmoney", sourceRecordId="source-001")
    provenance = Provenance(recordClass=ProvenanceClass.STANDARDIZED)
    storage = MemoryStorage(clock=lambda: CAPTURED_AT)

    stored = storage.put(
        key,
        {"title": "A document"},
        source=source,
        provenance=provenance,
        metadata={"sourceScope": "individual-stock"},
    )

    assert stored.key == key
    assert stored.dataset == "news.document"
    assert stored.source == source
    assert stored.provenance == provenance
    assert stored.metadata["sourceScope"] == "individual-stock"
    assert stored.stored_at == CAPTURED_AT


def test_memory_storage_supports_structured_and_document_payloads():
    storage = MemoryStorage(clock=lambda: CAPTURED_AT)
    record = StandardRecord.model_validate(
        {
            "dataset": MARKET_QUOTE_DATASET.name,
            "schemaVersion": MARKET_QUOTE_DATASET.schema_version,
            "recordId": "SSE:600519@2026-09-20",
            "entityId": INSTRUMENT,
            "capturedAt": CAPTURED_AT,
            "source": {"providerId": "synthetic"},
            "status": "live",
            "quality": {},
            "provenance": {"recordClass": "standardized"},
            "data": {"price": "1500.00"},
        }
    )
    financial = FinancialStatementData(
        instrumentId=INSTRUMENT,
        symbol="SSE:600519",
        statementType="balance_sheet",
        periods=[],
    )
    document = NewsDocumentData(
        documentId="eastmoney:news:001",
        sourceDocumentId="001",
        title="A title",
        publishedAt=CAPTURED_AT,
        url="https://example.invalid/news/001",
        contentAvailable=False,
        source="synthetic",
        relatedInstruments=[INSTRUMENT],
    )

    record_key = StorageKey.from_dataset(MARKET_QUOTE_DATASET, {"recordId": record.record_id})
    financial_key = StorageKey.from_dataset(
        FINANCIAL_STATEMENT_DATASET,
        {"instrument": INSTRUMENT, "statementType": "balance_sheet", "periodEnd": date(2026, 6, 30)},
    )
    document_key = StorageKey.from_dataset(NEWS_DOCUMENT_DATASET, {"documentId": "001"})

    storage.put(record_key, record)
    storage.put(financial_key, financial)
    storage.put(document_key, document)

    assert storage.get(record_key).data == record
    assert storage.get(financial_key).data == financial
    assert storage.get(document_key).data == document


def test_memory_storage_has_explicit_missing_and_replacement_semantics():
    storage = MemoryStorage(clock=lambda: CAPTURED_AT)
    key = StorageKey("market.quote", "1.0", {"recordId": "record-001"})

    assert storage.get(key) is None
    assert storage.exists(key) is False
    assert storage.delete(key) is False

    first = storage.put(key, {"value": 1})
    second = storage.put(key, {"value": 2})

    assert first.data == {"value": 1}
    assert second.data == {"value": 2}
    assert storage.get(key) == second
    assert storage.exists(key) is True
    assert storage.delete(key) is True
    assert storage.get(key) is None


def test_storage_operations_reject_non_keys_and_stored_at_requires_timezone():
    storage = MemoryStorage(clock=lambda: CAPTURED_AT)

    with pytest.raises(InvalidStorageKey):
        storage.get("market.quote/1.0/not-a-key")
    with pytest.raises(InvalidStorageKey):
        StorageKey("not a dataset", "1.0", {})
    with pytest.raises(InvalidStoredObject, match="timezone"):
        storage.put(
            StorageKey("market.quote", "1.0", {"recordId": "record-001"}),
            {},
            stored_at=datetime(2026, 9, 20, 9, 30),
        )


def test_storage_contract_has_no_refresh_or_freshness_policy_fields():
    public_methods = {name for name in dir(Storage) if not name.startswith("_")}
    put_parameters = set(inspect.signature(Storage.put).parameters)
    forbidden = {"ttl", "max_age", "refresh", "stale", "cache_hit", "cache_miss", "freshness"}

    assert public_methods == {"delete", "exists", "get", "put"}
    assert put_parameters.isdisjoint(forbidden)
