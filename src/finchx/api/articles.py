"""热门内容、同花顺话题目录与按来源读取的公开文章。"""

from finchx.sources.aigupiao import articles as agp_articles
from finchx.sources.tonghuashun import articles as ths_articles
from finchx.sources.tonghuashun import hot_content as ths_hot_content
from finchx.sources.tonghuashun import topic_articles as ths_topic_articles


class ArticlesAPI:
    """按来源顺序读取文章及其公开提供的内容。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def hot_content(self, content_type: str = "topic", limit: int = 20) -> list[dict]:
        """读取同花顺热门话题或热门文章。"""
        return ths_hot_content.hot_content(content_type, limit, timeout=self._timeout)

    def ths_list(self, topic_url: str, limit: int = 20) -> list[dict]:
        """读取同花顺社区话题关联的新闻与长文目录。"""
        return ths_topic_articles.ths_list(topic_url, limit, timeout=self._timeout)

    def ths_get(self, url: str) -> dict:
        """读取同花顺单篇公开新闻、长文、专题或视频。"""
        return ths_articles.ths_get(url, timeout=self._timeout)

    def agp_topic_articles(
        self, limit: int = 20, sort: str = "newest",
    ) -> list[dict]:
        """读取爱股票题材频道文章，包含来源正文。"""
        return agp_articles.agp_topic_articles(limit, sort, timeout=self._timeout)

    def agp_get(self, url: str) -> dict:
        """读取爱股票单篇公开文章及平台摘要、免责声明。"""
        return agp_articles.agp_get(url, timeout=self._timeout)
