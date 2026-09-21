"""Provider capability for historical daily Klines bars."""

from collections.abc import Sequence
from typing import Protocol

from finchx.contracts import Source
from finchx.datasets.market_klines import KlinesRequest, _ProviderKlineRow


class KlinesProvider(Protocol):
    @property
    def source(self) -> Source:
        """Identity of this direct provider endpoint."""
        ...

    def fetch_klines(self, request: KlinesRequest) -> Sequence[_ProviderKlineRow]:
        """Fetch the requested daily series without creating StandardRecords."""
        ...
