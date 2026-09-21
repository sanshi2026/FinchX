"""Provider capability for market ranking requests."""

from collections.abc import Sequence
from typing import Protocol

from finchx.contracts import Source
from finchx.datasets.market_ranking import (
    MarketRankingRequest,
    _ProviderRankingRow,
)


class MarketRankingProvider(Protocol):
    @property
    def source(self) -> Source:
        """Identity of this direct provider."""
        ...

    def fetch_ranking(
        self,
        request: MarketRankingRequest,
    ) -> Sequence[_ProviderRankingRow]:
        """Fetch ranked rows for the requested universe and criterion."""
        ...
