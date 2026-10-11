"""SSE JSON POST 与显式禁重定向的认证请求边界。"""

import json
from urllib.error import HTTPError

import pytest

from finchx import SourceError
from finchx._common import http


class Response:
    def __init__(self, body, status=200):
        self.body, self.status, self.closed = body, status, False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def read(self):
        return self.body


@pytest.mark.parametrize("method,body,expected", [(http.post_text, 'data: {"正文":"原文"}\n\n', 'data: {"正文":"原文"}\n\n'),
                                                (http.post_json, '{"业务":0}', {"业务": 0})])
def test_credential_requests_use_no_redirect_handler_once(monkeypatch, method, body, expected):
    calls, handlers = [], []
    response = Response(body.encode())
    class Opener:
        def open(self, request, **kwargs):
            calls.append((request, kwargs))
            return response
    def build(handler):
        handlers.append(handler)
        return Opener()
    monkeypatch.setattr(http, "build_opener", build)
    monkeypatch.setattr(http, "urlopen", lambda *a, **k: pytest.fail("凭据请求不应进入默认重定向请求"))
    headers = {"Cookie": "invalid-offline-test=1"}
    kwargs = {} if method is http.post_text else {"follow_redirects": False}
    assert method("https://example.invalid", data={"条件": "中文"}, timeout=2, headers=headers, source="测试", **kwargs) == expected
    request, arguments = calls[0]
    assert request.get_method() == "POST" and json.loads(request.data) == {"条件": "中文"}
    assert request.get_header("Cookie") == headers["Cookie"] and arguments == {"timeout": 2}
    assert request.get_header("Content-type") == "application/json" and response.closed
    assert len(handlers) == 1 and isinstance(handlers[0], http._NoRedirects)
    assert handlers[0].redirect_request(request, None, 302, "", {"Location": "https://example.invalid/next"}, "https://example.invalid/next") is None


def test_redirect_http_error_is_not_followed_or_retried(monkeypatch):
    calls = []
    class Opener:
        def open(self, request, **kwargs):
            calls.append(request)
            raise HTTPError(request.full_url, 302, "redirect", {"Location": "https://example.invalid/other"}, None)
    monkeypatch.setattr(http, "build_opener", lambda *a: Opener())
    with pytest.raises(SourceError, match="302"):
        http.post_text("https://example.invalid", data={}, timeout=1, headers={"Authorization": "Bearer invalid-test-key"}, source="测试")
    assert len(calls) == 1


@pytest.mark.parametrize("body,status", [(b"\xff", 200), (b"", 403), (b"", 500)])
def test_sse_decode_and_http_failure_are_explicit(monkeypatch, body, status):
    class Opener:
        def open(self, *args, **kwargs):
            return Response(body, status)
    monkeypatch.setattr(http, "build_opener", lambda *args: Opener())
    with pytest.raises(SourceError):
        http.post_text("https://example.invalid", data={}, timeout=1, headers={}, source="测试")
