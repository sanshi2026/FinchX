"""三来源研报聚合及各来源独立研报。"""

from finchx._common import reports as reports_fetch
from finchx.sources.aigupiao import reports_single as agp_reports
from finchx.sources.eastmoney import reports_single as em_reports
from finchx.sources.analysys import reports_single as analysys_reports


class ReportsAPI:
    """读取研报目录、来源摘要及 PDF 链接。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def fetch(self, keyword: str, limit: int = 20, start_date: str | None = None,
              end_date: str | None = None) -> dict:
        """跨来源原生检索研报，自动读取选中结果的摘要或网页正文。"""
        return reports_fetch.fetch(keyword, limit, start_date, end_date, timeout=self._timeout)

    def agp_fetch(
        self, limit: int = 20, kind: str = "all",
        keyword: str | None = None, industry: str | None = None, *,
        start_date: str | None = None, end_date: str | None = None,
    ) -> list[dict]:
        """读取爱股票研报目录及选中报告的网页摘要与 PDF 链接。"""
        return agp_reports.agp_fetch(
            limit, kind, keyword, industry, start_date=start_date,
            end_date=end_date, timeout=self._timeout,
        )

    def em_fetch(
        self, limit: int = 20, keyword: str | None = None,
        start_date: str | None = None, end_date: str | None = None,
    ) -> list[dict]:
        """读取东方财富研报目录及选中报告的网页摘要与 PDF 链接。"""
        return em_reports.em_fetch(
            limit, keyword, start_date, end_date, timeout=self._timeout,
        )

    def analysys_fetch(
        self, limit: int = 20, keyword: str | None = None,
        start_date: str | None = None, end_date: str | None = None,
    ) -> list[dict]:
        """读取易观原生目录或搜索结果及正式正文与 PDF 链接。"""
        return analysys_reports.analysys_fetch(
            limit, keyword, start_date, end_date, timeout=self._timeout,
        )
