"""Public, explicit query services for document datasets."""

from finchx.query.documents import DisclosureService, NewsService
from finchx.query.financial import FinancialStatementService
from finchx.query.forum import ForumService
from finchx.query.market_news import MarketNewsService
from finchx.query.articles import ArticleDetailService

news = NewsService()
disclosure = DisclosureService()
market_news = MarketNewsService()
forum = ForumService()
financial_statements = FinancialStatementService()

__all__ = ["ArticleDetailService", "DisclosureService", "FinancialStatementService", "ForumService", "MarketNewsService", "NewsService", "disclosure", "financial_statements", "forum", "market_news", "news"]
