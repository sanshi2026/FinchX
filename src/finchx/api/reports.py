"""爱股票研报目录与独立摘要。"""

from finchx.sources.aigupiao import reports as agp_reports


class ReportsAPI:
    """读取研报目录、来源摘要及 PDF 链接。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

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
