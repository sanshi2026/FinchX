"""三来源研报聚合及爱股票独立目录与摘要。"""

from finchx._common import reports as reports_fetch
from finchx.sources.aigupiao import reports as agp_reports


class ReportsAPI:
    """读取研报目录、来源摘要及 PDF 链接。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def fetch(self, keyword: str, limit: int = 20, start_date: str | None = None,
              end_date: str | None = None) -> dict:
        """跨来源原生检索研报，自动读取选中结果的摘要或网页正文。"""
        return reports_fetch.fetch(keyword, limit, start_date, end_date, timeout=self._timeout)

    def agp_list(
        self, limit: int = 20, kind: str = "all",
        keyword: str | None = None, industry: str | None = None,
    ) -> list[dict]:
        """按来源类别、关键词或行业读取研报目录。"""
        return agp_reports.agp_list(
            limit, kind, keyword, industry, timeout=self._timeout,
        )

    def agp_get(self, url: str) -> dict:
        """独立读取单篇研报的来源摘要与 PDF 链接。"""
        return agp_reports.agp_get(url, timeout=self._timeout)
