import pytest

from finchx.entities import (
    AmbiguousSymbolError,
    Exchange,
    InstrumentId,
    InstrumentKind,
    InvalidSymbolError,
    Market,
    format_symbol,
    normalize_instrument,
    normalize_symbol,
    parse_symbol,
)


@pytest.mark.parametrize("code", ["000001", "600519", "300750", "68A123"])
def test_bare_codes_are_ambiguous_without_context(code):
    with pytest.raises(AmbiguousSymbolError, match="bare symbol is ambiguous"):
        normalize_symbol(code)


def test_parse_canonical_symbol_and_round_trip():
    identity = parse_symbol("cn_a:sse:equity:600519")
    assert identity == InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )
    assert format_symbol(identity) == "cn_a:sse:equity:600519"
    assert parse_symbol(format_symbol(identity)) == identity


@pytest.mark.parametrize("code", ["A:B", "100%", "指数", "A:B 100%/指数"])
def test_round_trip_preserves_absent_exchange_and_encoded_code(code):
    identity = InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
    )
    canonical = format_symbol(identity)
    assert canonical.startswith("cn_a:-:index:")
    assert " " not in canonical
    assert parse_symbol(canonical) == identity


def test_normalize_accepts_explicit_context_without_inferring_fields():
    identity = normalize_symbol(
        "600519",
        market="CN_A",
        exchange="SSE",
        kind="EQUITY",
    )
    assert identity == InstrumentId(
        code="600519",
        market=Market.CN_A,
        exchange=Exchange.SSE,
        kind=InstrumentKind.EQUITY,
    )

    without_known_venue = normalize_symbol(
        "600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
    )
    assert without_known_venue.exchange is None


@pytest.mark.parametrize(
    "context",
    [
        {"exchange": "sse"},
        {"market": "cn_a"},
        {"kind": "equity"},
        {"market": "cn_a", "exchange": "sse"},
        {"exchange": "sse", "kind": "equity"},
    ],
)
def test_partial_context_is_ambiguous(context):
    with pytest.raises(AmbiguousSymbolError, match="market and kind are required"):
        normalize_symbol("600519", **context)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("market", "cn_b"),
        ("exchange", "sh"),
        ("kind", "fund"),
    ],
)
def test_unknown_explicit_enum_token_is_invalid(field, value):
    context = {"market": "cn_a", "kind": "equity"}
    context[field] = value
    with pytest.raises(InvalidSymbolError, match=f"unknown {field}"):
        normalize_symbol("600519", **context)


def test_empty_code_and_non_string_symbols_are_invalid():
    with pytest.raises(InvalidSymbolError, match="must not be empty"):
        normalize_symbol("", market="cn_a", kind="equity")
    with pytest.raises(InvalidSymbolError, match="must be a string"):
        normalize_symbol(600519, market="cn_a", kind="equity")


@pytest.mark.parametrize(
    "symbol",
    [
        " cn_a:sse:equity:600519",
        "cn_a:sse:equity:600519 ",
        "600 519",
        "cn_a:sse:equity:",
    ],
)
def test_whitespace_is_not_trimmed_and_empty_canonical_code_is_invalid(symbol):
    with pytest.raises(InvalidSymbolError):
        parse_symbol(symbol)


def test_canonical_tokens_are_case_insensitive_and_format_as_lowercase():
    identity = parse_symbol("CN_A:SSE:EQUITY:600519")
    assert identity.market is Market.CN_A
    assert format_symbol(identity) == "cn_a:sse:equity:600519"


def test_canonical_format_rejects_bad_enum_tokens_and_noncanonical_code_escapes():
    for symbol in (
        "cn_b:sse:equity:600519",
        "cn_a:sh:equity:600519",
        "cn_a:sse:fund:600519",
        "cn_a:sse:equity:bad%escape",
        "cn_a:sse:equity:bad%GG",
        "cn_a:sse:equity:bad%2",
        "cn_a:sse:equity:%FF",
        "cn_a:sse:equity:600519:extra",
    ):
        with pytest.raises(InvalidSymbolError):
            parse_symbol(symbol)


def test_provider_spellings_are_not_canonical_aliases():
    for provider_spelling in ("sh600519", "600519.SH", "SH.600519", "1.600519"):
        with pytest.raises(InvalidSymbolError):
            parse_symbol(provider_spelling)
        with pytest.raises(AmbiguousSymbolError):
            normalize_symbol(provider_spelling)


@pytest.mark.parametrize(
    ("code", "exchange"),
    [
        ("600519", Exchange.SSE),
        ("000001", Exchange.SZSE),
        ("300750", Exchange.SZSE),
    ],
)
def test_normalize_instrument_resolves_verified_bare_equity_codes(code, exchange):
    assert normalize_instrument(code) == InstrumentId(
        code=code,
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=exchange,
    )


@pytest.mark.parametrize("code", ["430001", "830001", "920001", "930001"])
def test_normalize_instrument_does_not_guess_bse_for_ambiguous_bare_codes(code):
    with pytest.raises(AmbiguousSymbolError, match="pass an explicit InstrumentId"):
        normalize_instrument(code)


def test_normalize_instrument_accepts_explicit_bse_identity():
    identity = InstrumentId(
        code="920001",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.BSE,
    )
    assert normalize_instrument(identity) is identity


def test_normalize_instrument_preserves_explicit_identity_and_does_not_guess_index():
    index = InstrumentId(
        code="000001",
        market=Market.CN_A,
        kind=InstrumentKind.INDEX,
        exchange=Exchange.SZSE,
    )
    assert normalize_instrument(index) is index
    assert normalize_instrument("000001").kind is InstrumentKind.EQUITY


@pytest.mark.parametrize("value", ["60051", "6005190", "60A519", "600 519", "600519.SH"])
def test_normalize_instrument_rejects_invalid_bare_inputs(value):
    with pytest.raises(InvalidSymbolError, match="six-digit ASCII code"):
        normalize_instrument(value)


def test_normalize_instrument_rejects_exchange_ambiguous_six_digit_code():
    with pytest.raises(AmbiguousSymbolError, match="does not identify an exchange"):
        normalize_instrument("199999")


def test_identity_shape_does_not_check_real_world_existence():
    identity = normalize_symbol(
        "999999",
        market="cn_a",
        exchange="sse",
        kind="equity",
    )
    assert identity.code == "999999"


def test_canonical_symbol_cannot_be_combined_with_context():
    with pytest.raises(InvalidSymbolError, match="do not combine"):
        normalize_symbol("cn_a:sse:equity:600519", market="cn_a", kind="equity")


def test_canonical_symbol_with_conflicting_context_is_rejected():
    with pytest.raises(InvalidSymbolError, match="do not combine"):
        normalize_symbol(
            "cn_a:sse:equity:600519",
            market="cn_a",
            exchange="szse",
            kind="equity",
        )
