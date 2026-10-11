"""公开客户端。"""

import math

from finchx.api.reference import ReferenceAPI
from finchx.api.market import MarketAPI
from finchx.api.fund_flow import FundFlowAPI
from finchx.api.sector import SectorAPI
from finchx.api.company import CompanyAPI
from finchx.api.financial import FinancialAPI
from finchx.api.regulation import RegulationAPI
from finchx.api.hotlist import HotlistAPI
from finchx.api.fupan import FupanAPI
from finchx.api.news import NewsAPI
from finchx.api.articles import ArticlesAPI
from finchx.api.disclosure import DisclosureAPI
from finchx.api.reports import ReportsAPI
from finchx.api.forum import ForumAPI
from finchx.api.iwencai import IwencaiAPI


class FinchX:
    """每次调用直接取数；timeout 为每次 HTTP 请求的超时秒数。"""

    def __init__(self, timeout: float = 15.0) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout 必须是有限的正数（秒）")
        try:
            seconds = float(timeout)
        except OverflowError as exc:
            raise ValueError("timeout 必须是有限的正数（秒）") from exc
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("timeout 必须是有限的正数（秒）")
        self.reference = ReferenceAPI(timeout=seconds)
        self.market = MarketAPI(timeout=seconds)
        self.fund_flow = FundFlowAPI(timeout=seconds)
        self.sector = SectorAPI(timeout=seconds)
        self.company = CompanyAPI(timeout=seconds)
        self.financial = FinancialAPI(timeout=seconds)
        self.regulation = RegulationAPI(timeout=seconds)
        self.hotlist = HotlistAPI(timeout=seconds)
        self.fupan = FupanAPI(timeout=seconds)
        self.news = NewsAPI(timeout=seconds)
        self.articles = ArticlesAPI(timeout=seconds)
        self.disclosure = DisclosureAPI(timeout=seconds)
        self.reports = ReportsAPI(timeout=seconds)
        self.forum = ForumAPI(timeout=seconds)
        self.iwencai = IwencaiAPI(timeout=seconds)
