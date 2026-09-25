"""Unit vocabulary for future dataset contracts.

Money and ratios use Decimal in Python and decimal strings in JSON so values
remain exact across serialization. Dataset schemas must state the currency
for each monetary field; FinchX's first A-share contracts use CNY.
"""

from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer, ValidationInfo


_DECIMAL_PATTERN = r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$"


def _validate_decimal_input(value: object, info: ValidationInfo) -> object:
    if info.mode == "json" and not isinstance(value, str):
        raise ValueError("decimal JSON values must be strings")
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, str) and re.fullmatch(_DECIMAL_PATTERN, value):
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid decimal string") from exc
    else:
        raise ValueError("use a Decimal or a canonical decimal string, not a float or integer")
    if not decimal_value.is_finite():
        raise ValueError("decimal values must be finite")
    return value


def _decimal_to_wire(value: Decimal) -> str:
    return format(value, "f")


class Currency(str, Enum):
    CNY = "CNY"


DecimalString = Annotated[
    Decimal,
    BeforeValidator(_validate_decimal_input, json_schema_input_type=str),
    PlainSerializer(_decimal_to_wire, return_type=str, when_used="json"),
]


Price = Annotated[
    DecimalString,
    Field(
        description="Price per share; currency is CNY.",
        examples=["12.34"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
IndexPoints = Annotated[
    DecimalString,
    Field(
        description="An index level or change expressed in index points, not CNY per share.",
        examples=["1310.13"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
Amount = Annotated[
    DecimalString,
    Field(
        description="Monetary amount in CNY.",
        examples=["123456.78"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
Percentage = Annotated[
    DecimalString,
    Field(
        description="A ratio fraction, not percentage points: 4.24% is 0.0424.",
        examples=["0.0424"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
ValuationMultiple = Annotated[
    DecimalString,
    Field(
        description=(
            "A valuation multiple expressed in times. Finite negative values are allowed."
        ),
        examples=["-5.25"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
Ratio = Annotated[
    DecimalString,
    Field(
        description="A dimensionless ratio expressed in times; 2.35 means 2.35x.",
        examples=["2.35"],
        json_schema_extra={"pattern": _DECIMAL_PATTERN},
    ),
]
ShareQuantity = Annotated[
    DecimalString,
    Field(description="Exact share quantity that may contain a fractional average or per-ten-share value.", examples=["2.50"], json_schema_extra={"pattern": _DECIMAL_PATTERN}),
]
Shares = Annotated[
    int,
    Field(
        strict=True,
        ge=0,
        description="A non-negative whole number of shares.",
        examples=[100],
    ),
]
