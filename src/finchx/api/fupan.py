"""题材复盘接口。"""

from finchx.sources.jiuyangongshe import replay


class FupanAPI:
    """读取来源提供的题材复盘。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def jygs_replay(self, date: str | None = None, *, session: str, headless: bool = False) -> dict:
        """读取韭研公社题材复盘；默认显示临时浏览器，session 仅用于本次请求。"""
        return replay.jygs_replay(date, session=session, headless=headless, timeout=self._timeout)
