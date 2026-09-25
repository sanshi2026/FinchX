"""Provider capability for market-wide quote snapshots."""

from collections.abc import Sequence
from typing import Protocol

from finchx.contracts import Source
from finchx.datasets.market_quote import (
    MarketQuoteUniverseRequest,
    _ProviderQuoteRow,
)


class MarketQuoteProvider(Protocol):
    @property
    def source(self) -> Source:
        """Identity of this direct provider."""
        ...

    def fetch_quotes(
        self,
        request: MarketQuoteUniverseRequest,
    ) -> Sequence[_ProviderQuoteRow]:
        """Fetch one quote snapshot for the requested universe."""
        ...
