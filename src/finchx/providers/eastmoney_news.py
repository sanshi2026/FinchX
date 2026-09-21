"""Compatibility import for the EastMoney news Provider."""

from finchx.providers.eastmoney_documents import (
    EASTMONEY_NEWS_DETAIL_ENDPOINT,
    EASTMONEY_NEWS_LIST_ENDPOINT,
    EastmoneyNewsProvider,
)

__all__ = ["EASTMONEY_NEWS_DETAIL_ENDPOINT", "EASTMONEY_NEWS_LIST_ENDPOINT", "EastmoneyNewsProvider"]
