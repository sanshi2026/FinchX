"""Declarative, transport-independent dataset definitions."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import TypeAdapter, ValidationError

from finchx.contracts.dataset import DatasetId


RequestT = TypeVar("RequestT")
DataT = TypeVar("DataT")

_DATASET_ID_ADAPTER = TypeAdapter(DatasetId)


@dataclass(frozen=True)
class DatasetDefinition(Generic[RequestT, DataT]):
    """Name and type metadata for a dataset; it does not execute requests."""

    name: DatasetId
    schema_version: str
    request_type: type[RequestT]
    data_type: type[DataT]

    def __post_init__(self) -> None:
        try:
            validated_name = _DATASET_ID_ADAPTER.validate_python(self.name)
        except ValidationError as exc:
            raise ValueError(f"invalid dataset name: {self.name!r}") from exc
        object.__setattr__(self, "name", validated_name)

        if not isinstance(self.schema_version, str):
            raise TypeError("schema_version must be a string")
        if not self.schema_version or self.schema_version != self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string without outer whitespace")
        if not isinstance(self.request_type, type):
            raise TypeError("request_type must be a class")
        if not isinstance(self.data_type, type):
            raise TypeError("data_type must be a class")
