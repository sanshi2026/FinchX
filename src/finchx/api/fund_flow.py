"""股票资金流与龙虎榜接口。"""

from finchx.sources.aigupiao import dragon_tiger
from finchx.sources.tencent import fund_flow as tencent


class FundFlowAPI:
    """读取股票资金流、龙虎榜事件与席位。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def stock(self, code: str, days: int = 20) -> dict:
        """读取沪深股票资金流，days 为最近日线窗口，范围 1 至 50。"""
        return tencent.stock(code, days=days, timeout=self._timeout)

    def dragon_tiger_list(self, date: str) -> list[dict]:
        """读取指定日期的全部来源龙虎榜事件。"""
        return dragon_tiger.dragon_tiger_list(date, timeout=self._timeout)

    def dragon_tiger_detail(self, code: str, date: str, trade_id: str) -> dict:
        """读取一个龙虎榜事件的成交摘要与买卖营业部席位。"""
        return dragon_tiger.dragon_tiger_detail(code, date, trade_id, timeout=self._timeout)
