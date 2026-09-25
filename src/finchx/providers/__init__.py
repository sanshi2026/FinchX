"""Dataset-specific provider capabilities."""

from finchx.providers.errors import ProviderError
from finchx.providers.jiuyangongshe_replay import JiyangongsheReplayProvider
from finchx.providers.eastmoney_market import (
    EastmoneyBreadthProvider,
    EastmoneyBrokenLimitPoolProvider,
    EastmoneyLimitDownPoolProvider,
    EastmoneyLimitUpPoolProvider,
    EastmoneyStrongPoolProvider,
    EastmoneyYesterdayLimitUpPoolProvider,
)
from finchx.providers.eastmoney_stock_keyword import EastMoneyStockKeywordProvider
from finchx.providers.instrument import InstrumentListingProvider, InstrumentProvider
from finchx.providers.market_klines import KlinesProvider
from finchx.providers.market_quote import MarketQuoteProvider
from finchx.providers.market_ranking import MarketRankingProvider
from finchx.providers.tencent import TencentMarketProvider
from finchx.providers.tencent_quote import TencentQuoteProvider
from finchx.providers.tencent_fund_flow import TencentFundFlowProvider
from finchx.providers.tencent_industry import TencentIndustryComparisonProvider
from finchx.providers.tencent_intraday import TencentIntradayProvider
from finchx.providers.tencent_klines import TencentKlinesProvider
from finchx.providers.tencent_sector import TencentSectorProvider
from finchx.providers.tencent_f10 import TencentF10Provider
from finchx.providers.tencent_float_holder import TencentFloatHolderProvider
from finchx.providers.eastmoney_documents import EastmoneyDisclosureProvider, EastmoneyNewsProvider
from finchx.providers.market_news import (
    AigupiaoMarketNewsProvider,
    BaiduFinscopeMarketNewsProvider,
    EastmoneyMarketNewsProvider,
)
from finchx.providers.tonghuashun_financial import TonghuashunFinancialProvider
from finchx.providers.aigupiao_market_intelligence import (
    AigupiaoDragonTigerProvider,
    AigupiaoMarketSentimentProvider,
    AigupiaoSeriesLimitUpProvider,
)
from finchx.providers.sohu_klines import SohuKlinesProvider
from finchx.providers.trading_calendar import (
    PmcTradingCalendarProvider,
    SzseTradingCalendarProvider,
    TradingCalendarProvider,
)
from finchx.providers.taoguba_forum import TaogubaForumProvider
from finchx.providers.iwencai import IwencaiProvider
from finchx.providers.tonghuashun_concept import TonghuashunConceptProvider
from finchx.providers.ths_hotlist import THSHotListProvider
from finchx.providers.ths_articles import (
    ARTICLE_PROVIDER_ID,
    ArticleDetailSourceError,
    THSArticleDetailProvider,
    encode_news_seq,
)
from finchx.providers.ths_topic_articles import THSTopicArticlesProvider

_REGISTRY_EXPORTS = {
    "DatasetRoutingSemantics",
    "ProviderRegistry",
    "ProviderSpec",
    "PROVIDER_REGISTRY",
    "PROVIDER_SPECS",
}


def __getattr__(name: str):
    if name in _REGISTRY_EXPORTS:
        from finchx.providers import registry

        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "EastmoneyDisclosureProvider",
    "EastmoneyNewsProvider",
    "AigupiaoMarketNewsProvider",
    "BaiduFinscopeMarketNewsProvider",
    "EastmoneyMarketNewsProvider",
    "TonghuashunFinancialProvider",
    "AigupiaoDragonTigerProvider",
    "AigupiaoMarketSentimentProvider",
    "AigupiaoSeriesLimitUpProvider",
    "EastmoneyBreadthProvider",
    "EastmoneyBrokenLimitPoolProvider",
    "EastmoneyLimitDownPoolProvider",
    "EastmoneyLimitUpPoolProvider",
    "EastmoneyStrongPoolProvider",
    "EastmoneyYesterdayLimitUpPoolProvider",
    "EastMoneyStockKeywordProvider",
    "InstrumentListingProvider",
    "InstrumentProvider",
    "MarketQuoteProvider",
    "KlinesProvider",
    "MarketRankingProvider",
    "PmcTradingCalendarProvider",
    "ProviderError",
    "JiyangongsheReplayProvider",
    "SzseTradingCalendarProvider",
    "TradingCalendarProvider",
    "TencentMarketProvider",
    "TencentQuoteProvider",
    "TencentFundFlowProvider",
    "TencentIndustryComparisonProvider",
    "TencentIntradayProvider",
    "TencentKlinesProvider",
    "TencentSectorProvider",
    "TencentF10Provider",
    "TencentFloatHolderProvider",
    "SohuKlinesProvider",
    "IwencaiProvider",
    "TonghuashunConceptProvider",
    "THSHotListProvider",
    "ArticleDetailSourceError",
    "THSArticleDetailProvider",
    "THSTopicArticlesProvider",
]
