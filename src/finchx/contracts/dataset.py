"""Shared, extensible identity type for FinchX datasets."""

from typing import Annotated, TypeAlias

from pydantic import StringConstraints


DATASET_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._][a-z][a-z0-9_]*)*$"

DatasetId: TypeAlias = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, pattern=DATASET_ID_PATTERN),
]
"""A validated dataset name compatible with StandardRecord.dataset."""
