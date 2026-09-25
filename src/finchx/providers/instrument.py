"""Dataset-specific provider capabilities for instrument data."""

from collections.abc import Sequence
from typing import Protocol

from finchx.contracts import Source
from finchx.datasets.instrument import (
    InstrumentRequest,
    InstrumentUniverseRequest,
    _ProviderInstrumentRow,
)


class InstrumentProvider(Protocol):
    """Capability to fetch one explicitly identified instrument."""

    @property
    def source(self) -> Source:
        """Identity of this direct provider."""
        ...

    def fetch_instrument(
        self,
        request: InstrumentRequest,
    ) -> Sequence[_ProviderInstrumentRow]:
        """Fetch and parse source rows for one explicit identity."""
        ...


class InstrumentListingProvider(Protocol):
    """Capability to list instruments without changing exact-lookup semantics."""

    @property
    def source(self) -> Source:
        """Identity of this direct provider."""
        ...

    def list_instruments(
        self,
        request: InstrumentUniverseRequest,
    ) -> Sequence[_ProviderInstrumentRow]:
        """Fetch and parse provider rows for the requested universe."""
        ...
