"""标准 JSON POST 的编码、超时与传输错误边界。"""

from http.client import IncompleteRead
import json
from urllib.error import HTTPError, URLError

import pytest

from finchx import SourceError
from finchx._common import http


class Response:
    def __init__(self, body=b'{"code":0}', status=200, error=None):
        self.body, self.status, self.error = body, status, error
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self):
        if self.error is not None:
            raise self.error
        return self.body


def test_post_method_utf8_chinese_json_content_type_and_timeout(monkeypatch):
    calls = []
    headers = {"Referer": "https://quote.eastmoney.com/", "X-Test": "value"}
    response = Response(json.dumps({"关键词": "白酒"}, ensure_ascii=False).encode())
    def opener(request, **kwargs):
        calls.append((request, kwargs))
        return response
    monkeypatch.setattr(http, "urlopen", opener)
    result = http.post_json("https://example.invalid/source", data={"关键词": "白酒", "zero": 0},
                            timeout=2.5, headers=headers, source="eastmoney")
    assert result == {"关键词": "白酒"}
    assert len(calls) == 1 and response.closed
    request, kwargs = calls[0]
    assert request.get_method() == "POST" and request.full_url == "https://example.invalid/source"
    assert "白酒".encode("utf-8") in request.data
    assert json.loads(request.data) == {"关键词": "白酒", "zero": 0}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Referer") == headers["Referer"]
    assert kwargs == {"timeout": 2.5}
    assert headers == {"Referer": "https://quote.eastmoney.com/", "X-Test": "value"}


@pytest.mark.parametrize("status", [200, 201, 299])
def test_successful_http_status_reads_json(monkeypatch, status):
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: Response(b'[]', status))
    assert http.post_json("https://example.invalid", data={}, timeout=1, headers={}, source="eastmoney") == []


@pytest.mark.parametrize("status", [199, 300, 401, 500])
def test_unsuccessful_response_status_keeps_source(monkeypatch, status):
    response = Response(status=status)
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(SourceError, match=str(status)) as caught:
        http.post_json("https://example.invalid", data={}, timeout=1, headers={}, source="eastmoney")
    assert caught.value.source == "eastmoney" and response.closed


@pytest.mark.parametrize("error", [
    HTTPError("https://example.invalid", 403, "拒绝", {}, None),
    URLError("不可达"), TimeoutError(), OSError("连接失败"), IncompleteRead(b"{", 20),
])
@pytest.mark.parametrize("during_read", [False, True])
def test_network_and_incomplete_http_errors_wrap_without_retry(monkeypatch, error, during_read):
    calls = []
    def opener(*args, **kwargs):
        calls.append(args)
        if during_read:
            return Response(error=error)
        raise error
    monkeypatch.setattr(http, "urlopen", opener)
    with pytest.raises(SourceError) as caught:
        http.post_json("https://example.invalid", data={}, timeout=1, headers={}, source="eastmoney")
    assert caught.value.source == "eastmoney" and caught.value.__cause__ is error
    assert len(calls) == 1


@pytest.mark.parametrize("body", [b"", b"not-json", b'{"data":', b'\xff'])
def test_invalid_json_or_encoding_wraps_source_error(monkeypatch, body):
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: Response(body))
    with pytest.raises(SourceError, match="不是有效的 JSON") as caught:
        http.post_json("https://example.invalid", data={}, timeout=1, headers={}, source="eastmoney")
    assert caught.value.source == "eastmoney"


@pytest.mark.parametrize("timeout", [True, None, "15", 0, -1, float("inf"), float("nan"), 10**1000])
def test_invalid_timeout_never_opens_request(monkeypatch, timeout):
    calls = []
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError):
        http.post_json("https://example.invalid", data={}, timeout=timeout, headers={}, source="eastmoney")
    assert calls == []


@pytest.mark.parametrize("data", [{"value": float("nan")}, {"value": set()}, {"value": "\ud800"}])
def test_invalid_request_json_never_opens_request(monkeypatch, data):
    calls = []
    monkeypatch.setattr(http, "urlopen", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(SourceError, match="请求数据"):
        http.post_json("https://example.invalid", data=data, timeout=1, headers={}, source="eastmoney")
    assert calls == []


def test_existing_get_helpers_keep_get_method_and_response_behavior(monkeypatch):
    calls = []
    def opener(request, **kwargs):
        calls.append(request)
        return Response(b'{"code":0}')
    monkeypatch.setattr(http, "urlopen", opener)
    assert http.get_json("https://example.invalid", timeout=1, headers={}, source="szse") == {"code": 0}
    assert http.get_text("https://example.invalid", timeout=1, headers={}, source="szse") == '{"code":0}'
    assert all(request.get_method() == "GET" and request.data is None for request in calls)


def test_form_post_utf8_encoding_content_type_zero_and_timeout(monkeypatch):
    from urllib.parse import parse_qs
    calls=[]
    response=Response('{"名称":"汽车行业"}'.encode())
    class Opener:
        def open(self,request,**kwargs):
            calls.append((request,kwargs))
            return response
    handlers=[]
    def build(handler):
        handlers.append(handler)
        return Opener()
    monkeypatch.setattr(http,"build_opener",build)
    headers={"Referer":"https://report.aigupiao.com/","Content-Type":"application/json"}
    data={"keyword":"汽车 行业+增长","limit":20,"u_id":0}
    assert http.post_form_json("https://example.invalid",data=data,timeout=2.5,headers=headers,source="aigupiao")=={"名称":"汽车行业"}
    request,kwargs=calls[0]
    assert request.get_method()=="POST"
    assert parse_qs(request.data.decode("ascii"))=={"keyword":["汽车 行业+增长"],"limit":["20"],"u_id":["0"]}
    assert request.get_header("Content-type")=="application/x-www-form-urlencoded"
    assert request.get_header("Referer")==headers["Referer"]
    assert headers["Content-Type"]=="application/json" and data["u_id"]==0
    assert kwargs=={"timeout":2.5} and response.closed
    assert len(handlers)==1 and isinstance(handlers[0],http._NoRedirects)


@pytest.mark.parametrize("status,body,error",[
    (403,b'{}',None),(503,b'{}',None),(200,b'not-json',None),
    (200,b'\xff',None),(200,b'{}',TimeoutError()),
    (200,b'{}',IncompleteRead(b'{',20)),
])
def test_form_post_wraps_http_json_and_read_errors_without_retry(monkeypatch,status,body,error):
    calls=[]
    response=Response(body,status,error)
    class Opener:
        def open(self,request,**kwargs):
            calls.append(request)
            return response
    monkeypatch.setattr(http,"build_opener",lambda handler:Opener())
    with pytest.raises(SourceError) as caught:
        http.post_form_json("https://example.invalid",data={},timeout=1,headers={},source="aigupiao")
    assert caught.value.source=="aigupiao" and len(calls)==1 and response.closed
    if error is not None:assert caught.value.__cause__ is error


@pytest.mark.parametrize("method",["post","get"])
@pytest.mark.parametrize("status",[301,302,303,307,308])
def test_no_redirect_transports_never_open_destination(monkeypatch,method,status):
    from email.message import Message
    from io import BytesIO
    from urllib.request import HTTPHandler, build_opener
    from urllib.response import addinfourl
    calls=[]
    class Transport(HTTPHandler):
        def http_open(self,request):
            calls.append(request.full_url)
            headers=Message()
            headers["Location"]="http://other.invalid/restricted"
            response=addinfourl(BytesIO(b""),headers,request.full_url,status)
            response.msg="redirect"
            return response
    monkeypatch.setattr(http,"build_opener",lambda handler:build_opener(handler,Transport()))
    with pytest.raises(SourceError,match=str(status)) as caught:
        if method=="post":
            http.post_form_json("http://source.invalid/list",data={},timeout=1,headers={},source="aigupiao")
        else:
            http.get_text("http://source.invalid/detail",timeout=1,headers={},source="aigupiao",follow_redirects=False)
    assert caught.value.source=="aigupiao"
    assert calls==["http://source.invalid/"+("list" if method=="post" else "detail")]


@pytest.mark.parametrize("data,timeout,error",[
    ([],1,SourceError),({"keyword":"\ud800"},1,SourceError),({},True,ValueError),({},0,ValueError),
])
def test_invalid_form_or_timeout_never_opens_transport(monkeypatch,data,timeout,error):
    calls=[]
    monkeypatch.setattr(http,"build_opener",lambda *args:calls.append(args))
    with pytest.raises(error):
        http.post_form_json("http://example.invalid",data=data,timeout=timeout,headers={},source="aigupiao")
    assert calls==[]
