"""同花顺股票、板块、转债与 ETF 热榜。"""

from finchx.sources.tonghuashun import hotlist as ths_hotlist


class HotlistAPI:
    """读取当前热榜或候选池的来源热度排行。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def stocks(
        self, category: str = "popular", period: str | None = None,
        limit: int | None = 20,
    ) -> list[dict]:
        """按类别和周期读取股票热榜。"""
        return ths_hotlist.stocks(category, period, limit, timeout=self._timeout)

    def sectors(self, sector_type: str = "concept", limit: int | None = 20) -> list[dict]:
        """读取概念、行业或指数板块热榜。"""
        return ths_hotlist.sectors(sector_type, limit, timeout=self._timeout)

    def convertible_bonds(self, limit: int | None = 20) -> list[dict]:
        """读取可转债热榜。"""
        return ths_hotlist.convertible_bonds(limit, timeout=self._timeout)

    def etfs(self, category: str = "popular", limit: int | None = 20) -> list[dict]:
        """按候选池读取 ETF 热度排行。"""
        return ths_hotlist.etfs(category, limit, timeout=self._timeout)
