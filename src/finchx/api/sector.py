"""股票与概念板块接口。"""

from datetime import date

from finchx.sources.eastmoney import keywords
from finchx.sources.tencent import sector as tencent
from finchx.sources.tonghuashun import concept


class SectorAPI:
    """读取股票板块资料与概念行情。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def tx_sectors(self, code: str) -> list[dict]:
        """读取腾讯财经提供的股票所属板块。"""
        return tencent.tx_sectors(code, timeout=self._timeout)

    def em_keywords(self, code: str) -> list[dict]:
        """读取东方财富提供的股票关键词。"""
        return keywords.em_keywords(code, timeout=self._timeout)

    def tx_industry_comparison(self, code: str) -> dict:
        """读取腾讯财经提供的股票行业对比。"""
        return tencent.tx_industry_comparison(code, timeout=self._timeout)

    def ths_concept_list(self) -> list[dict]:
        """读取同花顺概念目录。"""
        return concept.ths_concept_list(timeout=self._timeout)

    def ths_concept_quote_snapshot(self, code: str) -> dict:
        """读取同花顺概念点位快照。"""
        return concept.ths_concept_quote_snapshot(code, timeout=self._timeout)

    def ths_concept_ohlcv(self, code: str, start_date: date | str, end_date: date | str) -> list[dict]:
        """读取同花顺概念日线。"""
        return concept.ths_concept_ohlcv(code, start_date, end_date, timeout=self._timeout)
