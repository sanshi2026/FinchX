"""FinchX: an independent Python package for A-share market data."""

__version__ = "1.0.0"

from finchx.collector import Collector
from finchx.client import CLIENT_ENDPOINTS, FinchX
from finchx.query import (
    DisclosureService, FinancialStatementService, MarketNewsService, NewsService,
    disclosure, financial_statements, market_news, news,
)

__all__ = ["Collector", "FinchX", "CLIENT_ENDPOINTS", "DisclosureService", "FinancialStatementService", "MarketNewsService", "NewsService", "disclosure", "financial_statements", "market_news", "news", "__version__"]
