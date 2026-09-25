"""Stable acquisition, freshness, outcome, and estimate statuses for records."""

from enum import Enum


class DataStatus(str, Enum):
    """Record-level state; provenance separately describes the data layer."""

    LIVE = "live"
    DELAYED = "delayed"
    REUSED = "reused"
    MISSING = "missing"
    FAILED = "failed"
    ESTIMATED = "estimated"
