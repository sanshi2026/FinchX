"""FinchX: an independent Python package for A-share market data."""

__version__ = "2.0.0"

from finchx.collector import Collector
from finchx.client import CLIENT_ENDPOINTS, FinchX
from finchx.query.articles import ArticleDetailService
from finchx.query import (
    DisclosureService, FinancialStatementService, ForumService, MarketNewsService,
    NewsService, disclosure, financial_statements, forum, market_news, news,
)

__all__ = ["ArticleDetailService", "Collector", "FinchX", "CLIENT_ENDPOINTS", "DisclosureService", "FinancialStatementService", "ForumService", "MarketNewsService", "NewsService", "disclosure", "financial_statements", "forum", "market_news", "news", "__version__"]
