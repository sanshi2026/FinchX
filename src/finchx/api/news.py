"""来源新闻列表与东方财富新闻正文。"""

from finchx.sources.aigupiao import news as agp_news
from finchx.sources.baidu import news as bd_news
from finchx.sources.eastmoney import news as em_news


class NewsAPI:
    """按来源读取新闻及其实际发布时间。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def agp_list(
        self, limit: int = 20, since: str | None = None, until: str | None = None,
    ) -> list[dict]:
        """读取爱股票新闻，可限定数量与北京时间范围。"""
        return agp_news.agp_list(limit, since, until, timeout=self._timeout)

    def bd_list(
        self, limit: int = 20, since: str | None = None, until: str | None = None,
    ) -> list[dict]:
        """读取百度财经新闻，可限定数量与北京时间范围。"""
        return bd_news.bd_list(limit, since, until, timeout=self._timeout)

    def em_list(
        self, code: str, limit: int = 20,
        since: str | None = None, until: str | None = None,
    ) -> list[dict]:
        """读取东方财富个股相关新闻，可限定数量与北京时间范围。"""
        return em_news.em_list(code, limit, since, until, timeout=self._timeout)

    def em_get(self, url: str) -> dict:
        """读取东方财富新闻列表链接指向的单篇正文。"""
        return em_news.em_get(url, timeout=self._timeout)
