"""题材复盘接口。"""

from finchx.sources.jiuyangongshe import replay, replay_ego


class FupanAPI:
    """读取来源提供的题材复盘。"""

    def __init__(self, *, timeout: float) -> None:
        self._timeout = timeout

    def jygs_replay(self, date: str | None = None, *, session: str, headless: bool = False) -> dict:
        """读取韭研公社题材复盘；默认显示临时浏览器，session 仅用于本次请求。"""
        return replay.jygs_replay(date, session=session, headless=headless, timeout=self._timeout)

    def jygs_replay_ego(self, date: str | None = None) -> dict:
        """通过 Ego 浏览器读取韭研公社题材复盘。"""
        return replay_ego.jygs_replay_ego(date, timeout=self._timeout)
