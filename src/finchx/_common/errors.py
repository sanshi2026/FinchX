"""来源异常及整段回退失败上下文。"""


class FinchXError(Exception):
    """取数失败；errors 保留各来源失败的异常对象。"""

    def __init__(self, message: str, *, errors: tuple["SourceError", ...] = ()) -> None:
        super().__init__(message)
        self.errors = errors


class SourceError(FinchXError):
    """单个来源失败；source 与 reason 可供调用方检查。"""

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"{source} 来源失败：{reason}")
