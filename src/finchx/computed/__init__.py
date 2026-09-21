"""Narrow deterministic computed capabilities."""

from finchx.computed.deviation import (
    COMPUTED_DEVIATION_DATASET,
    DEFAULT_DEVIATION_KLINE_PROVIDER,
    DEVIATION_RULE_VERSION,
    BenchmarkSpec,
    DeviationData,
    DeviationRequest,
    DeviationService,
    DeviationWindowConvention,
    DeviationWindowData,
    PricePoint,
    calculate_deviation,
    resolve_deviation_benchmark,
)

__all__ = [
    "BenchmarkSpec",
    "COMPUTED_DEVIATION_DATASET",
    "DEFAULT_DEVIATION_KLINE_PROVIDER",
    "DEVIATION_RULE_VERSION",
    "DeviationData",
    "DeviationRequest",
    "DeviationService",
    "DeviationWindowConvention",
    "DeviationWindowData",
    "PricePoint",
    "calculate_deviation",
    "resolve_deviation_benchmark",
]
