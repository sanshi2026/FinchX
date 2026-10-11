"""标准库 HTTP 请求，不保存缓存或认证信息。"""

import json
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from finchx._common.convert import validate_timeout
from finchx._common.errors import SourceError

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def get_bytes(url: str, *, timeout: float, headers: dict[str, str], source: str) -> bytes:
    """完整读取二进制响应，不解码、不写文件。"""
    seconds = validate_timeout(timeout)
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=seconds) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            if response.status == 206:
                raise SourceError(source, "响应只包含部分内容")
            body = response.read()
            if not isinstance(body, bytes):
                raise SourceError(source, "响应不是有效的二进制内容")
            length = response.headers.get("Content-Length")
            if length is not None:
                if not isinstance(length, str) or not length.isascii() or not length.isdecimal():
                    raise SourceError(source, "响应 Content-Length 无效")
                try:
                    expected_length = int(length)
                except ValueError as exc:
                    raise SourceError(source, "响应 Content-Length 无效") from exc
                if len(body) != expected_length:
                    raise SourceError(source, "响应内容长度不完整")
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    return body


def get_json(url: str, *, timeout: float, headers: dict[str, str], source: str) -> Any:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            body = response.read()
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceError(source, "响应不是有效的 JSON") from exc


def get_text(
    url: str, *, timeout: float, headers: dict[str, str], source: str,
    encoding: str | None = None, follow_redirects: bool = True,
) -> str:
    """读取来源文本；编码由接口明确指定，默认 UTF-8。"""
    request = Request(url, headers=headers, method="GET")
    try:
        open_request = urlopen if follow_redirects else build_opener(_NoRedirects()).open
        with open_request(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            body = response.read()
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    try:
        return body.decode(encoding or "utf-8")
    except (UnicodeDecodeError, LookupError) as exc:
        raise SourceError(source, "响应文本编码无效") from exc


def post_form_json(
    url: str, *, data: dict, timeout: float, headers: dict[str, str], source: str,
    follow_redirects: bool = False,
) -> Any:
    """以 UTF-8 表单请求来源 JSON，默认拒绝重定向。"""
    seconds = validate_timeout(timeout)
    if not isinstance(data, dict):
        raise SourceError(source, "请求数据不是有效的表单")
    try:
        body = urlencode(data, encoding="utf-8", errors="strict").encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SourceError(source, "请求数据不是有效的表单") from exc
    request = Request(url, data=body, headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        open_request = urlopen if follow_redirects else build_opener(_NoRedirects()).open
        with open_request(request, timeout=seconds) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            body = response.read()
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceError(source, "响应不是有效的 JSON") from exc


def post_json(
    url: str, *, data: Any, timeout: float, headers: dict[str, str], source: str,
    follow_redirects: bool = True,
) -> Any:
    """以 UTF-8 JSON 发送一次 POST，并按现有 HTTP 错误语义读取 JSON。"""
    seconds = validate_timeout(timeout)
    try:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SourceError(source, "请求数据不是有效的 JSON") from exc
    request = Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        open_request = urlopen if follow_redirects else build_opener(_NoRedirects()).open
        with open_request(request, timeout=seconds) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            body = response.read()
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SourceError(source, "响应不是有效的 JSON") from exc


def post_text(
    url: str, *, data: Any, timeout: float, headers: dict[str, str], source: str,
    follow_redirects: bool = False,
) -> str:
    """以 UTF-8 JSON 请求来源文本（含 SSE），默认拒绝重定向。"""
    seconds = validate_timeout(timeout)
    try:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SourceError(source, "请求数据不是有效的 JSON") from exc
    request = Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        open_request = urlopen if follow_redirects else build_opener(_NoRedirects()).open
        with open_request(request, timeout=seconds) as response:
            if not 200 <= response.status < 300:
                raise SourceError(source, f"HTTP 请求失败（状态码 {response.status}）")
            body = response.read()
    except HTTPError as exc:
        raise SourceError(source, f"HTTP 请求失败（状态码 {exc.code}）") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise SourceError(source, f"网络请求失败（{type(exc).__name__}）") from exc
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceError(source, "响应文本编码无效") from exc
