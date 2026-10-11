"""基础工具接口及来源选择。"""

from datetime import date
import warnings

from finchx._common.convert import parse_date_parameter
from finchx._common.errors import FinchXError, SourceError
from finchx._common import pdf
from finchx.sources.szse import calendar as szse
from finchx.sources.pandas_market_calendars import calendar as pmc


class ReferenceAPI:
    """交易日历与 PDF 文字层提取等基础工具。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def pdf_text(self, url: str) -> dict:
        """读取 PDF 原生书签及全部页面文字层。"""
        return pdf.pdf_text(url, timeout=self._timeout)

    def trading_calendar(
        self,
        start_date: date | str,
        end_date: date | str,
        *,
        source: str = "auto",
    ) -> list[dict[str, str | bool]]:
        """返回包含首尾的每个自然日；自动回退覆盖整个请求。"""
        start = parse_date_parameter(start_date, "start_date", allow_date_object=True)
        end = parse_date_parameter(end_date, "end_date", allow_date_object=True)
        if start > end:
            raise ValueError("start_date 不得晚于 end_date")
        if not isinstance(source, str) or source not in {"auto", "szse", "pandas_market_calendars"}:
            raise ValueError("source 必须是 auto、szse 或 pandas_market_calendars")
        if source == "pandas_market_calendars":
            return pmc.trading_calendar(start, end)
        if source == "szse":
            return szse.trading_calendar(start, end, timeout=self._timeout)
        try:
            return szse.trading_calendar(start, end, timeout=self._timeout)
        except SourceError as primary_error:
            try:
                rows = pmc.trading_calendar(start, end)
            except SourceError as fallback_error:
                raise FinchXError(
                    f"交易日历的两个来源均失败：{primary_error}；{fallback_error}",
                    errors=(primary_error, fallback_error),
                ) from fallback_error
            warnings.warn(
                "交易日历整段请求已改用 pandas_market_calendars 的 SSE 离线日历；"
                f"主来源失败原因：{primary_error}",
                UserWarning,
                stacklevel=2,
            )
            return rows
