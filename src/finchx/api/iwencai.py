"""问财条件选股、文档搜索与正文读取。"""

from finchx.sources.iwencai import report as wc_report
from finchx.sources.iwencai import search as wc_search
from finchx.sources.iwencai import selection as wc_selection


class IwencaiAPI:
    """读取问财来源的业务结果，认证参数仅用于当次调用。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def select(
        self, query: str, limit: int = 100, *, cookies: str | dict[str, str],
    ) -> list[dict]:
        """按自然语言条件选股，保留来源动态指标。"""
        return wc_selection.select(query, limit, cookies=cookies, timeout=self._timeout)

    def search(
        self, query: str, channel: str = "report", limit: int = 50, *, api_key: str,
    ) -> list[dict]:
        """按来源语义顺序搜索研报、公告或新闻。"""
        return wc_search.search(query, channel, limit, api_key=api_key, timeout=self._timeout)

    def get_report(self, url: str, *, uid: str | None = None, channel: str | None = None) -> dict:
        """读取网页正文或问财文字快照；纯 PDF 返回原文链接。"""
        return wc_report.get_report(url, uid=uid, channel=channel, timeout=self._timeout)
