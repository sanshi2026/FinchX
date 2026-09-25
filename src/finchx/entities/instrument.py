"""Explicit instrument identity types. This module does not parse symbols."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Market(str, Enum):
    CN_A = "cn_a"


class Exchange(str, Enum):
    SSE = "sse"
    SZSE = "szse"
    BSE = "bse"


class InstrumentKind(str, Enum):
    EQUITY = "equity"
    INDEX = "index"
    ETF = "etf"


class InstrumentId(BaseModel):
    """Identity for an instrument whose code, market, and kind are already known."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str = Field(min_length=1, pattern=r".*\S.*")
    market: Market
    kind: InstrumentKind
    exchange: Exchange | None = None

    @field_validator("code")
    @classmethod
    def code_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must contain a non-whitespace character")
        return value
