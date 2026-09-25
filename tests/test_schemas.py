import json
from decimal import Decimal

import pytest
import jsonschema
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter, ValidationError

from finchx.datasets import (
    TopicArticleData,
    ArticleDetailData,
    InstrumentData,
    MarketKlineData,
    EquityIntradayData,
    IndexIntradayData,
    MarketOrderbookData,
    MarketFundFlowDailyData,
    MarketFundFlowIntradayData,
    MarketFundFlowSnapshotData,
    MarketInstrumentSectorSnapshotData,
    MarketStockKeywordData,
    ConceptRef,
    ConceptQuoteSnapshotData,
    ConceptOhlcvData,
    MarketIndustryComparisonData,
    MarketBreadthData,
    MarketLimitUpPoolData,
    MarketLimitDownPoolData,
    MarketYesterdayLimitUpPoolData,
    MarketStrongPoolData,
    MarketBrokenLimitPoolData,
    MarketQuoteData,
    MarketQuoteSnapshotData,
    MarketRankingData,
    TradingCalendarData,
)
from finchx.computed import DeviationData
from finchx.contracts import (
    Amount,
    Currency,
    DataStatus,
    Percentage,
    Price,
    Ratio,
    Shares,
    Provenance,
    Quality,
    Source,
    SourceReference,
    StandardRecord,
    ValuationMultiple,
)
from finchx.entities import InstrumentId
from finchx.schemas import iter_schema_resources, read_schema, read_schema_resource, schema_root


SCHEMA_DIR = schema_root()


def load_schemas():
    return {
        path.name: read_schema(path.name)
        for path in iter_schema_resources()
    }


def schema_registry(schemas):
    from referencing import Registry, Resource

    registry = Registry()
    for schema in schemas.values():
        registry = registry.with_resource(
            schema["$id"],
            Resource.from_contents(schema),
        )
    return registry


def test_all_versioned_schemas_are_valid_2020_12_schemas():
    for schema in load_schemas().values():
        Draft202012Validator.check_schema(schema)


def test_synthetic_examples_and_python_serializations_match_envelope_schema():
    schemas = load_schemas()
    envelope = schemas["standard-record.schema.json"]
    validator = Draft202012Validator(
        envelope,
        registry=schema_registry(schemas),
        format_checker=jsonschema.FormatChecker(),
    )

    example_paths = sorted((SCHEMA_DIR / "examples").iterdir(), key=lambda path: path.name)
    assert {path.name for path in example_paths} == {
        "standard-record.json",
        "status-estimated.json",
        "status-failed.json",
        "status-missing.json",
    }

    for path in example_paths:
        example = json.loads(read_schema_resource(f"examples/{path.name}"))
        validator.validate(example)
        model = StandardRecord.model_validate(example)
        serialized = model.model_dump(mode="json", by_alias=True)
        validator.validate(serialized)

    estimated = json.loads(read_schema_resource("examples/status-estimated.json"))
    for record_class in ("standardized", "derived"):
        candidate = {**estimated, "provenance": {"recordClass": record_class}}
        validator.validate(candidate)
        StandardRecord.model_validate(candidate)

    base = json.loads(read_schema_resource("examples/standard-record.json"))
    invalid_timestamps = [
        "2026-09-17 09:30:00+08:00",
        "2026-09-17T09:30+08:00",
        "2026-09-17T09:30:00+0800",
        "2026-09-17T09:30:00.1234567Z",
        1790213400,
    ]
    for invalid_timestamp in invalid_timestamps:
        candidate = {**base, "capturedAt": invalid_timestamp}
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(candidate)
        with pytest.raises(ValidationError):
            StandardRecord.model_validate(candidate)

    unasserted_format_validator = Draft202012Validator(
        envelope,
        registry=schema_registry(schemas),
    )
    naive_time = {**base, "capturedAt": "2026-09-17T09:30:00"}
    with pytest.raises(jsonschema.ValidationError):
        unasserted_format_validator.validate(naive_time)

    equivalent_local = {**base, "capturedAt": "2026-09-17T09:30:00+08:00"}
    equivalent_utc = {**base, "capturedAt": "2026-09-17T01:30:00Z"}
    for candidate in (equivalent_local, equivalent_utc):
        validator.validate(candidate)
        StandardRecord.model_validate(candidate)
    assert (
        StandardRecord.model_validate(equivalent_local).captured_at
        == StandardRecord.model_validate(equivalent_utc).captured_at
    )
    equivalent_lowercase_z = {**base, "capturedAt": "2026-09-17T01:30:00z"}
    validator.validate(equivalent_lowercase_z)
    lowercase_z_model = StandardRecord.model_validate(equivalent_lowercase_z)
    assert lowercase_z_model.captured_at == StandardRecord.model_validate(equivalent_utc).captured_at
    assert lowercase_z_model.model_dump(mode="json", by_alias=True)["capturedAt"] == "2026-09-17T01:30:00Z"


def test_model_fields_required_fields_aliases_and_enums_match_schema():
    schemas = load_schemas()
    pairs = {
        "article-detail.schema.json": ArticleDetailData,
        "topic-article.schema.json": TopicArticleData,
        "source.schema.json": Source,
        "source-reference.schema.json": SourceReference,
        "quality.schema.json": Quality,
        "provenance.schema.json": Provenance,
        "instrument-identity.schema.json": InstrumentId,
        "instrument.schema.json": InstrumentData,
        "market-klines.schema.json": MarketKlineData,
        "market-equity-intraday.schema.json": EquityIntradayData,
        "market-equity-intraday-5d.schema.json": EquityIntradayData,
        "market-index-intraday.schema.json": IndexIntradayData,
        "market-index-intraday-5d.schema.json": IndexIntradayData,
        "market-quote-snapshot.schema.json": MarketQuoteSnapshotData,
        "market-orderbook.schema.json": MarketOrderbookData,
        "market-quote.schema.json": MarketQuoteData,
        "market-ranking.schema.json": MarketRankingData,
        "market-breadth.schema.json": MarketBreadthData,
        "market-limit-up-pool.schema.json": MarketLimitUpPoolData,
        "market-limit-down-pool.schema.json": MarketLimitDownPoolData,
        "market-yesterday-limit-up-pool.schema.json": MarketYesterdayLimitUpPoolData,
        "market-strong-pool.schema.json": MarketStrongPoolData,
        "market-broken-limit-pool.schema.json": MarketBrokenLimitPoolData,
        "market-stock-keyword.schema.json": MarketStockKeywordData,
        "market-concept-list.schema.json": ConceptRef,
        "market-concept-quote-snapshot.schema.json": ConceptQuoteSnapshotData,
        "market-concept-ohlcv.schema.json": ConceptOhlcvData,
        "market-deviation.schema.json": DeviationData,
        "trading-calendar.schema.json": TradingCalendarData,
        "standard-record.schema.json": StandardRecord,
    }

    for schema_name, model_type in pairs.items():
        canonical = schemas[schema_name]
        generated = model_type.model_json_schema(by_alias=True)
        expected_properties = set(generated.get("properties", {}))
        assert set(canonical.get("properties", {})) == expected_properties

        required_from_model = {
            field.alias or name
            for name, field in model_type.model_fields.items()
            if field.is_required()
        }
        assert set(canonical.get("required", [])) == required_from_model

    for schema_name, model_type in (
        ("market-equity-intraday.schema.json", EquityIntradayData),
        ("market-equity-intraday-5d.schema.json", EquityIntradayData),
        ("market-index-intraday.schema.json", IndexIntradayData),
        ("market-index-intraday-5d.schema.json", IndexIntradayData),
    ):
        canonical = schemas[schema_name]
        generated = model_type.model_json_schema(by_alias=True)["properties"]
        for field_name in ("tradeDate", "time", "price", "volume", "amount", "cumulativeVolume", "cumulativeAmount"):
            for constraint in ("type", "format", "pattern", "minimum"):
                if constraint in generated[field_name]:
                    assert canonical["properties"][field_name][constraint] == generated[field_name][constraint]

    envelope = schemas["standard-record.schema.json"]
    assert envelope["properties"]["schemaVersion"]["const"] == "1.0"
    assert envelope["properties"]["dataset"]["pattern"] == (
        StandardRecord.model_json_schema(by_alias=True)["properties"]["dataset"]["pattern"]
    )
    record_id_description = "FinchX-owned stable identity, distinct from a provider record ID."
    assert envelope["properties"]["recordId"]["description"] == record_id_description
    assert StandardRecord.model_json_schema(by_alias=True)["properties"]["recordId"]["description"] == record_id_description
    assert envelope["properties"]["status"]["enum"] == [status.value for status in DataStatus]
    assert schemas["quality.schema.json"]["properties"]["issues"]["items"]["properties"]["kind"]["enum"] == [
        "warning",
        "validation_concern",
        "stale",
        "partial",
        "estimated",
    ]
    assert schemas["provenance.schema.json"]["properties"]["recordClass"]["enum"] == [
        "raw",
        "standardized",
        "derived",
    ]


def test_decimal_unit_models_and_schemas_share_canonical_representation():
    units_schema = load_schemas()["units.schema.json"]
    decimal_cases = [
        ("Price", Price),
        ("Amount", Amount),
        ("Percentage", Percentage),
        ("Ratio", Ratio),
        ("ValuationMultiple", ValuationMultiple),
    ]

    for name, value_type in decimal_cases:
        decimal_schema = units_schema["$defs"][name]
        adapter = TypeAdapter(value_type)
        for mode in ("validation", "serialization"):
            generated_schema = adapter.json_schema(mode=mode)
            assert generated_schema["type"] == decimal_schema["type"] == "string"
            assert generated_schema["examples"] == decimal_schema["examples"]
            assert generated_schema["pattern"] == decimal_schema["pattern"]

        sample = decimal_schema["examples"][0]
        decimal_value = adapter.validate_python(Decimal(sample))
        wire_value = adapter.dump_python(decimal_value, mode="json")
        assert wire_value == sample
        jsonschema.validate(wire_value, decimal_schema)

    percentage_schema = units_schema["$defs"]["Percentage"]
    value = TypeAdapter(Percentage).validate_python("0.0424")
    wire_value = TypeAdapter(Percentage).dump_python(value, mode="json")
    assert Decimal(wire_value) == Decimal("0.0424")
    assert Decimal(wire_value) * Decimal("100") == Decimal("4.24")
    estimated_example = json.loads(
        (SCHEMA_DIR / "examples" / "status-estimated.json").read_text(encoding="utf-8")
    )
    example_ratio = estimated_example["data"]["changeRatio"]
    jsonschema.validate(example_ratio, percentage_schema)
    assert Decimal(example_ratio) == Decimal("0.0424")

    currency_schema = units_schema["$defs"]["Currency"]
    currency_adapter = TypeAdapter(Currency)
    assert currency_adapter.json_schema()["enum"] == currency_schema["enum"]
    jsonschema.validate(currency_adapter.dump_python(Currency.CNY, mode="json"), currency_schema)

    shares_schema = units_schema["$defs"]["Shares"]
    shares_adapter = TypeAdapter(Shares)
    shares_json_schema = shares_adapter.json_schema()
    assert shares_json_schema["type"] == shares_schema["type"] == "integer"
    assert shares_json_schema["minimum"] == shares_schema["minimum"] == 0
    jsonschema.validate(shares_adapter.dump_python(100, mode="json"), shares_schema)
    for invalid in ("100", 100.0, True, -1):
        with pytest.raises(ValidationError):
            shares_adapter.validate_python(invalid)


def test_market_quote_and_ranking_payload_schemas_validate_typed_contracts():
    schemas = load_schemas()
    registry = schema_registry(schemas)
    quote_validator = Draft202012Validator(
        schemas["market-quote.schema.json"],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    ranking_validator = Draft202012Validator(
        schemas["market-ranking.schema.json"],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )

    identity = {
        "code": "600519",
        "market": "cn_a",
        "kind": "equity",
        "exchange": "sse",
    }
    quote = MarketQuoteData(
        instrumentId=identity,
        price="1475.20",
        priceChange="-12.30",
        changeRate="-0.0083",
        changeRate5d="0.1234",
        changeRate10d="-0.055",
        changeRate20d="0.2",
        changeRate60d="-0.3",
        changeRate52w="1.25",
        changeRateYtd="0.05",
        amplitude="0.0825",
        volumeRatio="2.35",
        volume=1200,
        amount="0",
        peTtm="-5.25",
        mainNetInflow="-10000",
        mainInflow="20000",
        mainOutflow="30000",
        mainInflow5d="40000",
        mainOutflow5d="50000",
    )
    quote_wire = quote.model_dump(mode="json", by_alias=True)
    quote_validator.validate(quote_wire)
    assert quote_wire["changeRate5d"] == "0.1234"
    assert quote_wire["changeRate52w"] == "1.25"
    assert quote_wire["changeRateYtd"] == "0.05"
    assert quote_wire["amplitude"] == "0.0825"
    assert quote_wire["volumeRatio"] == "2.35"
    assert "priceToBook" not in quote_wire
    assert quote_wire["mainNetInflow"] == "-10000"
    assert quote_wire["mainInflow5d"] == "40000"
    assert MarketQuoteData.model_validate_json(quote.model_dump_json(by_alias=True)) == quote

    minimal_quote = {"instrumentId": identity, "price": "0"}
    quote_validator.validate(minimal_quote)
    for invalid_quote in (
        {"instrumentId": identity},
        {"instrumentId": identity, "price": 10.0},
        {"instrumentId": identity, "price": "1e2"},
        {"instrumentId": identity, "price": "10", "tencentFields": {}},
        {"instrumentId": identity, "price": "10", "priceToBook": "8.40"},
        {"instrumentId": identity, "price": "10", "volumeRatio": "-0.1"},
        {"instrumentId": identity, "price": "10", "volumeRatio": "-0"},
    ):
        with pytest.raises(jsonschema.ValidationError):
            quote_validator.validate(invalid_quote)
        with pytest.raises(ValidationError):
            MarketQuoteData.model_validate(invalid_quote)

    ranking = MarketRankingData.model_validate(
        {
            **quote_wire,
            "universe": "cn_a_share",
            "direction": "descending",
            "position": 1,
            "metric": {"criterion": "turnover", "value": "123456.78"},
        }
    )
    ranking_wire = ranking.model_dump(mode="json", by_alias=True)
    ranking_validator.validate(ranking_wire)
    assert set(quote_wire).issubset(ranking_wire)
    assert {field: ranking_wire[field] for field in quote_wire} == quote_wire
    assert MarketRankingData.model_validate_json(ranking.model_dump_json(by_alias=True)) == ranking

    invalid_metrics = (
        {"criterion": "turnover", "value": 123},
        {"criterion": "turnover", "value": "invalid"},
        {"criterion": "change_percent", "value": 3},
        {"criterion": "volume", "value": "100"},
        {"criterion": "volume", "value": 1.5},
    )
    for metric in invalid_metrics:
        payload = {
            **quote_wire,
            "universe": "cn_a_share",
            "direction": "descending",
            "position": 1,
            "metric": metric,
        }
        with pytest.raises(jsonschema.ValidationError):
            ranking_validator.validate(payload)
        with pytest.raises(ValidationError):
            MarketRankingData.model_validate(payload)


def test_instrument_payload_schema_validates_python_payload_and_rejects_provider_fields():
    schemas = load_schemas()
    schema = schemas["instrument.schema.json"]
    assert schema["properties"]["instrumentId"]["$ref"] == schemas[
        "instrument-identity.schema.json"
    ]["$id"]
    validator = Draft202012Validator(
        schema,
        registry=schema_registry(schemas),
    )
    payload = {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "exchange": "sse",
            "kind": "equity",
        },
        "name": "贵州茅台",
    }

    validator.validate(payload)
    model = InstrumentData.model_validate(payload)
    serialized = model.model_dump(mode="json", by_alias=True)
    validator.validate(serialized)

    invalid = {**payload, "vendor_internal_code": "vendor-001"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)
    with pytest.raises(ValidationError):
        InstrumentData.model_validate(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [("market", "cn_b"), ("exchange", "unknown"), ("kind", "warrant")],
)
def test_instrument_payload_schema_and_model_reject_unknown_identity_tokens(field, value):
    schemas = load_schemas()
    validator = Draft202012Validator(
        schemas["instrument.schema.json"],
        registry=schema_registry(schemas),
    )
    payload = {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "exchange": "sse",
            "kind": "equity",
        },
        "name": "贵州茅台",
    }
    invalid = {
        **payload,
        "instrumentId": {**payload["instrumentId"], field: value},
    }

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)
    with pytest.raises(ValidationError):
        InstrumentData.model_validate(invalid)


@pytest.mark.parametrize("name", ["", " ", None])
def test_instrument_payload_schema_and_model_reject_empty_or_null_name(name):
    schemas = load_schemas()
    validator = Draft202012Validator(
        schemas["instrument.schema.json"],
        registry=schema_registry(schemas),
    )
    payload = {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "exchange": "sse",
            "kind": "equity",
        },
        "name": name,
    }

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)
    with pytest.raises(ValidationError):
        InstrumentData.model_validate(payload)


def test_instrument_payload_schema_and_model_require_name():
    schemas = load_schemas()
    validator = Draft202012Validator(
        schemas["instrument.schema.json"],
        registry=schema_registry(schemas),
    )
    payload = {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "exchange": "sse",
            "kind": "equity",
        }
    }

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)
    with pytest.raises(ValidationError):
        InstrumentData.model_validate(payload)


def test_trading_calendar_payload_schema_is_minimal_and_rejects_provider_fields():
    schema = load_schemas()["trading-calendar.schema.json"]
    assert set(schema["properties"]) == {"date", "isTradingDay"}
    assert set(schema["required"]) == {"date", "isTradingDay"}
    assert schema["additionalProperties"] is False

    valid = TradingCalendarData(
        date="2026-09-17",
        isTradingDay=True,
    ).model_dump(mode="json", by_alias=True)
    jsonschema.validate(valid, schema, format_checker=jsonschema.FormatChecker())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {**valid, "holidayName": "invented provider field"},
            schema,
            format_checker=jsonschema.FormatChecker(),
        )


def test_quote_snapshot_and_orderbook_schemas_validate_contract_models():
    from finchx.datasets import MarketOrderbookData, MarketQuoteSnapshotData

    schemas = load_schemas()
    registry = schema_registry(schemas)
    snapshot_validator = Draft202012Validator(
        schemas["market-quote-snapshot.schema.json"],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    orderbook_validator = Draft202012Validator(
        schemas["market-orderbook.schema.json"],
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    identity = {
        "code": "600519",
        "market": "cn_a",
        "kind": "equity",
        "exchange": "sse",
    }
    snapshot = MarketQuoteSnapshotData(
        instrumentId=identity,
        price="1259.56",
        previousClose="1266.98",
        open="1262.99",
        high="1265.88",
        low="1256.10",
        priceChange="-7.42",
        changeRate="-0.0059",
        volume=1_737_300,
        amount="2188587296.0000",
        sourceTimestamp="2026-09-18T14:13:27+08:00",
    )
    snapshot_wire = snapshot.model_dump(mode="json", by_alias=True)
    snapshot_validator.validate(snapshot_wire)
    assert MarketQuoteSnapshotData.model_validate(snapshot_wire) == snapshot
    assert Decimal(snapshot_wire["changeRate"]) == Decimal("-0.0059")

    book = MarketOrderbookData(
        instrumentId=identity,
        bids=[{"level": 1, "price": "1259.21", "size": 700}],
        asks=[{"level": 1, "price": "1259.82", "size": 100}],
    )
    book_wire = book.model_dump(mode="json", by_alias=True)
    orderbook_validator.validate(book_wire)
    assert MarketOrderbookData.model_validate(book_wire) == book
    with pytest.raises(jsonschema.ValidationError):
        orderbook_validator.validate(
            {**book_wire, "bids": [{"level": 1, "price": "0", "size": 0}]}
        )
    index_identity = {
        "code": "000001",
        "market": "cn_a",
        "kind": "index",
        "exchange": "sse",
    }
    with pytest.raises(jsonschema.ValidationError):
        orderbook_validator.validate({**book_wire, "instrumentId": index_identity})
    with pytest.raises(ValidationError):
        MarketOrderbookData(instrumentId=index_identity, bids=[], asks=[])


def test_market_klines_schema_and_python_payload_stay_synchronized():
    from finchx.datasets import KlineAdjustment

    schemas = load_schemas()
    schema = schemas["market-klines.schema.json"]
    registry = schema_registry(schemas)
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    payload = {
        "instrumentId": {
            "code": "600519",
            "market": "cn_a",
            "kind": "equity",
            "exchange": "sse",
        },
        "barDate": "2025-06-12",
        "open": "1400.42",
        "high": "1404.29",
        "low": "1374.52",
        "close": "1379.42",
        "volume": 4990400,
        "amount": "7306800800.00",
        "adjustment": "qfq",
    }

    validator.validate(payload)
    model = MarketKlineData.model_validate(payload)
    assert model.model_dump(mode="json", by_alias=True) == payload

    nullable = {**payload, "amount": None}
    validator.validate(nullable)
    assert MarketKlineData.model_validate(nullable).amount is None
    without_amount = {key: value for key, value in payload.items() if key != "amount"}
    validator.validate(without_amount)
    assert MarketKlineData.model_validate(without_amount).amount is None

    assert schema["properties"]["barDate"]["format"] == "date"
    assert schema["properties"]["barDate"]["pattern"] == r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
    assert schema["properties"]["instrumentId"]["$ref"].endswith("/instrument-identity.schema.json")
    assert schema["properties"]["open"]["$ref"].endswith("/units.schema.json#/$defs/Price")
    assert schema["properties"]["volume"]["$ref"].endswith("/units.schema.json#/$defs/Shares")
    assert schema["properties"]["amount"]["anyOf"][0]["$ref"].endswith("/units.schema.json#/$defs/Amount")
    assert schema["properties"]["amount"]["anyOf"][1] == {"type": "null"}
    assert schema["additionalProperties"] is False
    assert "amount" not in schema["required"]
    assert "volume" in schema["required"]
    assert schema["properties"]["adjustment"]["enum"] == [
        item.value for item in KlineAdjustment
    ]

    invalid_values = (
        {**payload, "volume": None},
        {**payload, "adjustment": "split-adjusted"},
        {**payload, "barDate": "2025-02-30"},
        {**payload, "open": 1400.42},
        {**payload, "unexpected": "value"},
    )
    for invalid in invalid_values:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)
        with pytest.raises(ValidationError):
            MarketKlineData.model_validate(invalid)


def test_fund_flow_schemas_validate_contract_models_and_reject_provider_fields():
    schemas = load_schemas()
    registry = schema_registry(schemas)
    cases = (
        (
            "market-fund-flow-snapshot.schema.json",
            MarketFundFlowSnapshotData(
                instrumentId={
                    "code": "300434",
                    "market": "cn_a",
                    "exchange": "szse",
                    "kind": "equity",
                },
                tradeDate="2026-09-18",
                mainNetInflow="-79946700",
                mainInflow="332719852",
                mainOutflow="412666552",
                mainInflowRate="0.15",
                mainOutflowRate="0.19",
                retailInflow="743568337",
                retailOutflow="663621637",
                retailInflowRate="0.35",
                retailOutflowRate="0.31",
                superLargeNetInflow="-94785795",
                largeNetInflow="14839096",
                mediumNetInflow="22033969",
                smallNetInflow="57912730",
            ),
        ),
        (
            "market-fund-flow-intraday.schema.json",
            MarketFundFlowIntradayData(
                instrumentId={
                    "code": "300434",
                    "market": "cn_a",
                    "exchange": "szse",
                    "kind": "equity",
                },
                tradeDate="2026-09-18",
                time="15:00",
                price="12.25",
                cumulativeMainNetInflow="-79946700",
                cumulativeRetailNetInflow="79946700",
                cumulativeSuperLargeNetInflow="-94785795",
                cumulativeLargeNetInflow="14839096",
                cumulativeMediumNetInflow="22033969",
                cumulativeSmallNetInflow="57912730",
                cumulativeMainInflow="332719852",
                cumulativeMainOutflow="412666552",
            ),
        ),
        (
            "market-fund-flow-daily.schema.json",
            MarketFundFlowDailyData(
                instrumentId={
                    "code": "300434",
                    "market": "cn_a",
                    "exchange": "szse",
                    "kind": "equity",
                },
                tradeDate="2026-09-18",
                mainNetInflow="-79946700",
                close="12.25",
            ),
        ),
    )
    for schema_name, model in cases:
        schema = schemas[schema_name]
        validator = Draft202012Validator(
            schema,
            registry=registry,
            format_checker=jsonschema.FormatChecker(),
        )
        payload = model.model_dump(mode="json", by_alias=True)
        validator.validate(payload)
        assert type(model).model_validate(payload) == model
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({**payload, "vendor_internal_code": "not-public"})

    snapshot_schema = schemas["market-fund-flow-snapshot.schema.json"]
    snapshot_validator = Draft202012Validator(
        snapshot_schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    snapshot_payload = cases[0][1].model_dump(mode="json", by_alias=True)
    with pytest.raises(jsonschema.ValidationError):
        snapshot_validator.validate({**snapshot_payload, "mainInflowRate": "1.5"})
