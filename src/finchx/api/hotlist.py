"""Client namespace implementation: hotlist."""

from __future__ import annotations

from finchx.collectors import (
    FetchResult,
)
from finchx.contracts import (
    StandardRecord,
)
from finchx.datasets import (
    HOT_CONTENT_DATASET,
    HOT_CONVERTIBLE_BONDS_DATASET,
    HOT_ETFS_DATASET,
    HOT_SECTORS_DATASET,
    HOT_STOCKS_DATASET,
    HotContentRequest,
    HotConvertibleBondsRequest,
    HotEtfsRequest,
    HotSectorsRequest,
    HotStocksRequest,
)
from finchx.api._base import (
    _RequestNamespace,
)


class HotlistNamespace(_RequestNamespace):
    """Tonghuashun stock, sector, convertible-bond, ETF and content heat rankings."""

    def stocks(self, category: str = "popular", period: str | None = None, limit: int = 20, *,
               provider: str | None = None, use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotStocksRequest(category=category, period=period, limit=limit)
        return self._fetch_request(HOT_STOCKS_DATASET, request, provider=provider, use_cache=use_cache)

    def sectors(self, sector_type: str = "concept", limit: int = 20, *,
                provider: str | None = None, use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotSectorsRequest(sectorType=sector_type, limit=limit)
        return self._fetch_request(HOT_SECTORS_DATASET, request, provider=provider, use_cache=use_cache)

    def convertible_bonds(self, limit: int = 20, *, provider: str | None = None,
                          use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotConvertibleBondsRequest(limit=limit)
        return self._fetch_request(HOT_CONVERTIBLE_BONDS_DATASET, request, provider=provider, use_cache=use_cache)

    def etfs(self, category: str = "popular", limit: int = 20, *, provider: str | None = None,
             use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotEtfsRequest(category=category, limit=limit)
        return self._fetch_request(HOT_ETFS_DATASET, request, provider=provider, use_cache=use_cache)

    def content(self, content_type: str = "topic", limit: int = 20, *, provider: str | None = None,
                use_cache: bool | None = None) -> FetchResult[tuple[StandardRecord, ...]]:
        request = HotContentRequest(contentType=content_type, limit=limit)
        return self._fetch_request(HOT_CONTENT_DATASET, request, provider=provider, use_cache=use_cache)

# Preserve historical public type identities as implementation moves.
HotlistNamespace.__module__ = "finchx.client"
