"""Narrow deterministic computed capabilities."""

from finchx.computed.deviation import (
    COMPUTED_DEVIATION_DATASET,
    DEFAULT_DEVIATION_KLINE_PROVIDER,
    DEVIATION_RULE_VERSION,
    BenchmarkSpec,
    DeviationCoverageError,
    DeviationData,
    DeviationRequest,
    DeviationScenario,
    DeviationService,
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
    "DeviationCoverageError",
    "DeviationData",
    "DeviationRequest",
    "DeviationScenario",
    "DeviationService",
    "DeviationWindowData",
    "PricePoint",
    "calculate_deviation",
    "resolve_deviation_benchmark",
]
