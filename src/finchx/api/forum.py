"""淘股吧账户关注动态中的回复与文章。"""

from collections.abc import Mapping
from datetime import date

from finchx.sources.taoguba import forum as tgb_forum


class ForumAPI:
    """读取回复与文章全文，以及回复明确引用的父回复全文。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def tgb_replies(
        self, limit: int | None = 20,
        since: str | date | None = None, until: str | date | None = None,
        *, cookies: str | Mapping[str, str],
    ) -> list[dict]:
        """按数量和北京时间范围读取当前账户可见的回复与文章。"""
        return tgb_forum.tgb_replies(
            limit, since, until, cookies=cookies, timeout=self._timeout,
        )
