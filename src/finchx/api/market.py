"""市场行情接口。"""

from datetime import date

from finchx.sources.aigupiao import consecutive, sentiment
from finchx.sources.eastmoney import breadth, pools
from finchx.sources.tencent import intraday, klines, quote
from finchx.sources.tencent import market as tencent


class MarketAPI:
    """市场行情接口，直接返回所需业务数据。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def all_quotes(self) -> list[dict[str, str | float | int | None]]:
        """每次读取腾讯完整 A 股行情，直接返回业务字段。"""
        return tencent.all_quotes(timeout=self._timeout)

    def ranking(
        self,
        criterion: str = "change_percent",
        direction: str = "desc",
        limit: int | None = 50,
    ) -> list[dict[str, str | float | int | None]]:
        """使用腾讯来源排序读取所需排名；limit=None 时返回完整排名。"""
        if not isinstance(criterion, str) or criterion not in {"amount", "change_percent", "volume"}:
            raise ValueError("criterion 必须是 amount、change_percent 或 volume")
        if not isinstance(direction, str) or direction not in {"asc", "desc"}:
            raise ValueError("direction 必须是 asc 或 desc")
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise ValueError("limit 必须是正整数或 None")
        return tencent.ranking(criterion=criterion, direction=direction, limit=limit, timeout=self._timeout)

    def quote_snapshot(self, code: str, *, kind: str = "stock") -> dict:
        """读取单只股票或指数的行情快照。"""
        return quote.quote_snapshot(code, kind=kind, timeout=self._timeout)

    def ohlcv(
        self, code: str, start_date: date | str, end_date: date | str,
        adjustment: str | None = None, *, kind: str = "stock",
    ) -> list[dict]:
        """读取包含首尾日期的股票或指数日线。"""
        return klines.ohlcv(code, start_date, end_date, adjustment, kind=kind, timeout=self._timeout)

    def orderbook(self, code: str) -> dict:
        """读取股票买卖五档盘口。"""
        return quote.orderbook(code, timeout=self._timeout)

    def equity_intraday(self, code: str) -> list[dict]:
        """读取股票当日分时行情。"""
        return intraday.equity_intraday(code, timeout=self._timeout)

    def equity_intraday_5d(self, code: str) -> list[dict]:
        """读取股票近五日分时行情。"""
        return intraday.equity_intraday_5d(code, timeout=self._timeout)

    def index_intraday(self, code: str) -> list[dict]:
        """读取指数当日分时行情。"""
        return intraday.index_intraday(code, timeout=self._timeout)

    def index_intraday_5d(self, code: str) -> list[dict]:
        """读取指数近五日分时行情。"""
        return intraday.index_intraday_5d(code, timeout=self._timeout)

    def em_breadth(self) -> dict:
        """读取东方财富市场涨跌分布。"""
        return breadth.em_breadth(timeout=self._timeout)

    def agp_sentiment(self) -> dict[str, float | int | None]:
        """读取爱股票市场情绪指标。"""
        return sentiment.agp_sentiment(timeout=self._timeout)

    def limit_up_pool(self) -> list[dict]:
        """读取最新涨停池。"""
        return pools.limit_up_pool(timeout=self._timeout)

    def limit_down_pool(self) -> list[dict]:
        """读取最新跌停池。"""
        return pools.limit_down_pool(timeout=self._timeout)

    def broken_limit_pool(self) -> list[dict]:
        """读取最新炸板池。"""
        return pools.broken_limit_pool(timeout=self._timeout)

    def yesterday_limit_up_pool(self) -> list[dict]:
        """读取最新观察日期的昨日涨停池。"""
        return pools.yesterday_limit_up_pool(timeout=self._timeout)

    def strong_pool(self) -> list[dict]:
        """读取最新强势股池。"""
        return pools.strong_pool(timeout=self._timeout)

    def consecutive_limit_up(self) -> list[dict]:
        """读取最新连板股池。"""
        return consecutive.consecutive_limit_up(timeout=self._timeout)
