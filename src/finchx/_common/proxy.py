"""按客户端调用隔离 urllib 代理设置。"""

from contextvars import ContextVar
from functools import wraps
from urllib.request import ProxyHandler

_use_proxy = ContextVar("finchx_use_proxy", default=None)


def bind_api(cls):
    """为 API 方法绑定所属客户端的代理设置。"""
    def bind(method):
        @wraps(method)
        def call(self, *args, **kwargs):
            token = _use_proxy.set(getattr(self, "_use_proxy", True))
            try:
                return method(self, *args, **kwargs)
            finally:
                _use_proxy.reset(token)
        return call

    for name, method in vars(cls).copy().items():
        if not name.startswith("_") and callable(method):
            setattr(cls, name, bind(method))
    return cls


def warning_stacklevel(level):
    return level + (_use_proxy.get() is not None)


def thread_options():
    return {"initializer": _use_proxy.set, "initargs": (_use_proxy.get(),)}


def proxy_handlers():
    return () if _use_proxy.get() is not False else (ProxyHandler({}),)
