"""淘股吧账户关注动态中的回复与文章。"""


from collections.abc import Callable, Mapping
from datetime import date

from finchx._common.proxy import bind_api
from finchx.sources.taoguba import forum as tgb_forum


@bind_api
class ForumAPI:
    """读取回复与文章全文，以及回复明确引用的父回复全文。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def tgb_replies(
        self, limit: int | None = 20,
        since: str | date | None = None, until: str | date | None = None,
        *, cookies: str | Mapping[str, str],
        on_missing_reply: Callable[[dict[str, str | None]], object] | None = None,
    ) -> list[dict]:
        """读取当前账户内容；回调可跳过主题页与精确页均缺失的带引用回复。"""
        options = {"cookies": cookies, "timeout": self._timeout}
        if on_missing_reply is not None:
            options["on_missing_reply"] = on_missing_reply
        return tgb_forum.tgb_replies(
            limit, since, until, **options,
        )
