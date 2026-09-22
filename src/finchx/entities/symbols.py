"""Strict, provider-independent symbol normalization for InstrumentId."""

from enum import Enum
from typing import TypeAlias
from urllib.parse import quote, unquote_to_bytes

from pydantic import ValidationError

from finchx.entities.instrument import Exchange, InstrumentId, InstrumentKind, Market


class SymbolError(ValueError):
    """Base class for symbol parsing and normalization failures."""


class AmbiguousSymbolError(SymbolError):
    """The supplied symbol does not contain enough identity information."""


class InvalidSymbolError(SymbolError):
    """The symbol or one of its explicit identity fields is invalid."""


_NO_EXCHANGE = "-"
_CODE_SAFE_CHARACTERS = "-._~"
_BARE_EQUITY_EXCHANGE_PREFIXES = {
    Exchange.SSE: ("6",),
    Exchange.SZSE: ("0", "3"),
}

InstrumentInput: TypeAlias = InstrumentId | str


def _validate_symbol_text(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise InvalidSymbolError("symbol must be a string")
    if not symbol:
        raise InvalidSymbolError("symbol must not be empty")
    if any(character.isspace() for character in symbol):
        raise InvalidSymbolError("symbol must not contain whitespace; FinchX does not trim input")


def _coerce_enum(value: object, enum_type: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise InvalidSymbolError(f"{field_name} must be one of its declared tokens")
    try:
        return enum_type(value.casefold())
    except ValueError as exc:
        valid = ", ".join(item.value for item in enum_type)
        raise InvalidSymbolError(
            f"unknown {field_name} {value!r}; expected one of: {valid}"
        ) from exc


def _canonical_candidate(symbol: str) -> bool:
    parts = symbol.split(":", maxsplit=3)
    return len(parts) == 4 and parts[0].casefold() in {item.value for item in Market}


def _decode_code(encoded_code: str) -> str:
    try:
        code = unquote_to_bytes(encoded_code).decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidSymbolError("canonical code must contain valid UTF-8 percent-encoding") from exc
    if not code:
        raise InvalidSymbolError("canonical symbol code must not be empty")
    if _encode_code(code) != encoded_code:
        raise InvalidSymbolError("canonical code must use FinchX percent-encoding")
    return code


def _encode_code(code: str) -> str:
    return quote(code, safe=_CODE_SAFE_CHARACTERS)


def parse_symbol(symbol: str) -> InstrumentId:
    """Parse a FinchX canonical symbol into the existing InstrumentId model.

    Canonical form is market:exchange:kind:code. Tokens are case-insensitive;
    code is percent-encoded UTF-8 and remains case-sensitive. A dash denotes
    an intentionally unspecified exchange.
    """

    _validate_symbol_text(symbol)
    parts = symbol.split(":", maxsplit=3)
    if len(parts) != 4:
        raise InvalidSymbolError(
            "expected canonical symbol form market:exchange:kind:code"
        )

    market_text, exchange_text, kind_text, encoded_code = parts
    market = _coerce_enum(market_text, Market, "market")
    kind = _coerce_enum(kind_text, InstrumentKind, "kind")
    exchange = (
        None
        if exchange_text == _NO_EXCHANGE
        else _coerce_enum(exchange_text, Exchange, "exchange")
    )
    code = _decode_code(encoded_code)

    try:
        return InstrumentId(
            code=code,
            market=market,
            exchange=exchange,
            kind=kind,
        )
    except ValidationError as exc:
        raise InvalidSymbolError("canonical symbol does not form a valid InstrumentId") from exc


def format_symbol(instrument: InstrumentId) -> str:
    """Return the unique FinchX canonical symbol for an InstrumentId."""

    if not isinstance(instrument, InstrumentId):
        raise InvalidSymbolError("instrument must be an InstrumentId")
    exchange = instrument.exchange.value if instrument.exchange is not None else _NO_EXCHANGE
    return ":".join(
        (
            instrument.market.value,
            exchange,
            instrument.kind.value,
            _encode_code(instrument.code),
        )
    )


def normalize_symbol(
    symbol: str,
    *,
    market: Market | str | None = None,
    exchange: Exchange | str | None = None,
    kind: InstrumentKind | str | None = None,
) -> InstrumentId:
    """Normalize a canonical symbol or a code with explicit market and kind.

    Exchange may be omitted when it is genuinely unspecified. The function
    never infers a field from the code and performs no existence lookup.
    """

    _validate_symbol_text(symbol)
    has_context = market is not None or exchange is not None or kind is not None

    if _canonical_candidate(symbol):
        if has_context:
            raise InvalidSymbolError("do not combine a canonical symbol with explicit context")
        return parse_symbol(symbol)

    if not has_context:
        raise AmbiguousSymbolError(
            "a bare symbol is ambiguous; provide market and kind, plus exchange if known"
        )

    normalized_market = (
        _coerce_enum(market, Market, "market") if market is not None else None
    )
    normalized_exchange = (
        _coerce_enum(exchange, Exchange, "exchange") if exchange is not None else None
    )
    normalized_kind = (
        _coerce_enum(kind, InstrumentKind, "kind") if kind is not None else None
    )
    if normalized_market is None or normalized_kind is None:
        raise AmbiguousSymbolError(
            "market and kind are required; exchange is optional and is never inferred"
        )

    try:
        return InstrumentId(
            code=symbol,
            market=normalized_market,
            exchange=normalized_exchange,
            kind=normalized_kind,
        )
    except ValidationError as exc:
        raise InvalidSymbolError("explicit context does not form a valid InstrumentId") from exc


def normalize_instrument(value: InstrumentInput) -> InstrumentId:
    """Resolve a public instrument input into one explicit ``InstrumentId``.

    Existing ``InstrumentId`` values are returned unchanged. Canonical FinchX
    symbols are parsed as-is. A bare six-digit ASCII code is treated as a
    CN_A equity only when its leading digit identifies a supported exchange:
    6 -> SSE and 0/3 -> SZSE. The helper never guesses an
    index, ETF, or other instrument kind from a bare code.
    """

    if isinstance(value, InstrumentId):
        return value
    if not isinstance(value, str):
        raise InvalidSymbolError("instrument must be an InstrumentId or string")
    if ":" in value:
        return parse_symbol(value)
    if len(value) != 6 or not value.isascii() or not value.isdigit():
        raise InvalidSymbolError("bare instrument must be a six-digit ASCII code")

    exchange = next(
        (
            candidate
            for candidate, prefixes in _BARE_EQUITY_EXCHANGE_PREFIXES.items()
            if value.startswith(prefixes)
        ),
        None,
    )
    if exchange is None:
        raise AmbiguousSymbolError(
            "bare code does not identify an exchange; pass an explicit InstrumentId"
        )
    return InstrumentId(
        code=value,
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=exchange,
    )
