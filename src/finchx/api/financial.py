"""财务报表接口。"""

from finchx.sources.tonghuashun import financial


class FinancialAPI:
    """读取选定财务报表的报告期与业务科目。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def statements(self, code: str, statement: str, period_end: str | None = None,
                   max_periods: int | None = None) -> list[dict]:
        """读取一种报表，可精确选择报告期或截取最近报告期。"""
        return financial.statements(code, statement, period_end, max_periods,
                                    timeout=self._timeout)
