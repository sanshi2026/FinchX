"""Pure Decimal helpers for deviation thresholds and price rounding."""

from __future__ import annotations

from decimal import (
    Decimal,
    ROUND_CEILING,
)
from typing import (
    Literal,
)


def _upper_threshold(window_days: Literal[10, 30]) -> Decimal:
    return Decimal("1.00") if window_days == 10 else Decimal("2.00")


def _round_trigger_price_up(value: Decimal) -> Decimal:
    """Round a selected theoretical trigger price upward to the next cent."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
