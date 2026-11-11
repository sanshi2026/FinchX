"""客户端代理设置隔离及线程传播。"""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import inspect
import pickle
import threading
from urllib.error import HTTPError

import pytest

from finchx import FinchX
from finchx._common import http
from finchx._common.proxy import proxy_handlers, thread_options
from finchx.api import market


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/data")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.server.payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def servers(monkeypatch):
    target = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    target.payload = b'"direct"'
    proxy.payload = b'"proxy"'
    for server in (target, proxy):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    import urllib.request
    monkeypatch.setattr(urllib.request, "_opener", None)
    monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{proxy.server_port}")
    monkeypatch.setenv("no_proxy", "")
    try:
        yield f"http://127.0.0.1:{target.server_port}"
    finally:
        for server in (target, proxy):
            server.shutdown()
            server.server_close()


def test_instances_use_proxy_or_direct_without_global_changes(servers, monkeypatch):
    import urllib.request
    before = urllib.request._opener
    direct, default = FinchX(use_proxy=False), FinchX()
    def fetch(*, timeout):
        return http.get_json(servers + "/data", timeout=timeout, headers={}, source="test")
    monkeypatch.setattr(market.tencent, "all_quotes", fetch)
    assert direct.market.all_quotes() == "direct"
    assert urllib.request._opener is before
    assert default.market.all_quotes() == "proxy"
    assert direct.market.all_quotes() == "direct"
    assert default.market.all_quotes() == "proxy"
    assert inspect.ismethod(direct.market.all_quotes)
    assert pickle.loads(pickle.dumps(direct)).market._use_proxy is False


def test_nested_instances_and_thread_initializer(monkeypatch):
    direct, default = FinchX(use_proxy=False), FinchX()
    states = []
    def fetch(*, timeout):
        states.append(bool(proxy_handlers()))
        if len(states) == 1:
            with ThreadPoolExecutor(max_workers=1, **thread_options()) as executor:
                states.append(executor.submit(lambda: bool(proxy_handlers())).result())
            default.market.all_quotes()
            states.append(bool(proxy_handlers()))
        return []
    monkeypatch.setattr(market.tencent, "all_quotes", fetch)
    direct.market.all_quotes()
    assert states == [True, True, False, True]
    assert not proxy_handlers()


def test_direct_preserves_no_redirect(servers, monkeypatch):
    def fetch(*, timeout):
        return http.get_text(servers + "/redirect", timeout=timeout, headers={}, source="test", follow_redirects=False)
    monkeypatch.setattr(market.tencent, "all_quotes", fetch)
    from finchx import SourceError
    with pytest.raises(SourceError) as error:
        FinchX(use_proxy=False).market.all_quotes()
    assert isinstance(error.value.__cause__, HTTPError)
    assert error.value.__cause__.code == 302
