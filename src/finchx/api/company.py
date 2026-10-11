"""上市公司信息接口。"""

from finchx.sources.tencent import company


class CompanyAPI:
    """读取上市公司资料与财务概要及流通股东。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def info(self, code: str) -> dict:
        """一次读取上市公司资料、财务摘要、主营构成及财报行业对比。"""
        return company.info(code, timeout=self._timeout)

    def float_shareholders(self, code: str, year: int | None = None) -> list[dict]:
        """读取来源最近报告期或指定支持年份的流通股东。"""
        return company.float_shareholders(code, year, timeout=self._timeout)
