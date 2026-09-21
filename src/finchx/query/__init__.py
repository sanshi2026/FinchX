"""Public, explicit query services for document datasets."""

from finchx.query.documents import DisclosureService, NewsService
from finchx.query.financial import FinancialStatementService
from finchx.query.market_news import MarketNewsService

news = NewsService()
disclosure = DisclosureService()
market_news = MarketNewsService()
financial_statements = FinancialStatementService()

__all__ = ["DisclosureService", "FinancialStatementService", "MarketNewsService", "NewsService", "disclosure", "financial_statements", "market_news", "news"]
