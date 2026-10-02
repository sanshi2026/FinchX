"""Shared envelopes for provider row collections and partial pagination."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, overload


RowT = TypeVar("RowT")


@dataclass(frozen=True)
class _ProviderRowsResponse(Sequence[RowT], Generic[RowT]):
    """Rows plus provider-reported warnings and collection metadata."""

    rows: tuple[RowT, ...]
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.rows)

    @overload
    def __getitem__(self, index: int, /) -> RowT: ...

    @overload
    def __getitem__(self, index: slice, /) -> tuple[RowT, ...]: ...

    def __getitem__(self, index: int | slice, /) -> RowT | tuple[RowT, ...]:
        return self.rows[index]


@dataclass
class _PaginationStats:
    """Raw paging counts shared by providers that tolerate page overlap."""

    source_total: int | None = None
    source_row_count: int = 0
    duplicate_rows_skipped: int = 0

    def response(
        self,
        rows: Sequence[RowT],
        *,
        requested_count: int | None,
        source_label: str,
        result_kind: str,
    ) -> tuple[RowT, ...] | _ProviderRowsResponse[RowT]:
        unique_rows = tuple(rows)
        if self.duplicate_rows_skipped == 0:
            return unique_rows

        effective_requested_count = (
            self.source_total if requested_count is None else requested_count
        )
        if effective_requested_count is None or self.source_total is None:
            raise ValueError("partial pagination metadata requires a source total")
        warning = (
            f"{source_label} coverage is partial: returned {len(unique_rows)} unique rows "
            f"out of {effective_requested_count} requested after reading "
            f"{self.source_row_count} source rows; skipped {self.duplicate_rows_skipped} "
            f"cross-page duplicates. Rows are not a consistent point-in-time {result_kind}."
        )
        return _ProviderRowsResponse(
            rows=unique_rows,
            warnings=(warning,),
            metadata={
                "coverage_status": "partial",
                "requested_count": effective_requested_count,
                "source_row_count": self.source_row_count,
                "unique_count": len(unique_rows),
                "source_total": self.source_total,
                "duplicate_rows_skipped": self.duplicate_rows_skipped,
            },
        )
