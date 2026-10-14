"""监管信息接口。"""

from finchx.sources.eastmoney import regulation
from finchx.sources.tencent import deviation as deviation_source
from finchx.api.reference import ReferenceAPI


class RegulationAPI:
    """读取重点监控、异常波动记录及来源模型预测。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def watchlist(self) -> list[dict]:
        """读取来源完整重点监控证券名单。"""
        return regulation.watchlist(timeout=self._timeout)

    def abnormal_records(self, event_type: str = "ordinary") -> list[dict]:
        """读取普通或严重异常波动公告记录。"""
        return regulation.abnormal_records(event_type, timeout=self._timeout)

    def abnormal_prediction_history(self) -> list[dict]:
        """读取来源模型预测历史及来源标明的当前记录。"""
        return regulation.abnormal_prediction_history(timeout=self._timeout)

    def severe_predictions(self) -> list[dict]:
        """读取来源当前及次一交易日严重异动预测。"""
        return regulation.severe_predictions(timeout=self._timeout)

    def abnormal_counts(self) -> list[dict]:
        """读取来源十日内多次异常波动统计。"""
        return regulation.abnormal_counts(timeout=self._timeout)

    def deviation(self, code: str, windows=(10, 30), end_date: str | None = None,
                  *, reset_date: str | None = None) -> dict:
        """计算当日及次一交易日的最大偏离，并沿用同一区间基准计算触发价。"""
        return deviation_source.deviation(
            code, windows, end_date, reset_date=reset_date, timeout=self._timeout,
            calendar=ReferenceAPI(timeout=self._timeout).trading_calendar,
        )
