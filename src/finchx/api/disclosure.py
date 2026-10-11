"""东方财富公告目录与独立正文。"""

from datetime import date

from finchx.sources.eastmoney import disclosure as em_disclosure


class DisclosureAPI:
    """读取公告目录、来源正文与附件链接。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def em_list(
        self, code: str, limit: int = 20,
        since: str | date | None = None, until: str | date | None = None,
        categories: list[str] | tuple[str, ...] | None = None,
    ) -> list[dict]:
        """读取股票公告目录，可限定数量、北京时间范围与分类。"""
        return em_disclosure.em_list(
            code, limit, since, until, categories, timeout=self._timeout,
        )

    def em_get(self, url: str) -> dict:
        """读取单篇公告的来源正文及附件链接。"""
        return em_disclosure.em_get(url, timeout=self._timeout)
