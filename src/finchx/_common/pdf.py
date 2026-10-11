"""内存中的 PDF 文字层提取；PDFium 调用统一串行执行。"""

import ctypes
from importlib import import_module
from ipaddress import ip_address
import re
from threading import Lock
from urllib.parse import quote, urlsplit, urlunsplit
import warnings

from finchx._common.errors import SourceError
from finchx._common.http import DEFAULT_HEADERS, get_bytes

SOURCE = "pdf"
_PDFIUM_LOCK = Lock()


def _request_url(value: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value
            or any(c.isspace() or ord(c) < 33 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError("url 必须是合法的 HTTP(S) 绝对链接")
    try:
        value.encode("utf-8", errors="strict")
        parts = urlsplit(value)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None or parts.port == 0):
            raise ValueError
        authority = (r"\[[^\]]+\](?::[0-9]+)?" if parts.netloc.startswith("[")
                     else r"[^:\[\]]+(?::[0-9]+)?")
        if not re.fullmatch(authority, parts.netloc):
            raise ValueError
        if parts.netloc.startswith("["):
            bracketed_host = parts.netloc[1:].split("]", 1)[0]
            if bracketed_host.startswith("v"):
                if not re.fullmatch(r"v[0-9A-Fa-f]+\..+", bracketed_host):
                    raise ValueError
            elif ip_address(bracketed_host).version != 6:
                raise ValueError
        host = parts.hostname.encode("idna").decode("ascii")
        if any(c in host for c in "%/?#@"):
            raise ValueError
        # ASCII 查询（包括签名及百分号转义）保持原样；Unicode 仅做 URL 编码。
        netloc = f"[{host}]" if parts.netloc.startswith("[") else host
        if parts.port is not None:
            netloc += ":" + parts.netloc.rsplit(":", 1)[1]
        return urlunsplit((parts.scheme, netloc,
                          quote(parts.path, safe="/%:@!$&'()*+,;=-._~"),
                          quote(parts.query, safe="%=&[]:/?+;,@!$'()*~-._"), parts.fragment))
    except (ValueError, UnicodeError):
        raise ValueError("url 的主机、认证信息或端口无效") from None


def _outline(pdfium, document, page_count: int) -> list[dict]:
    """迭代原生书签树，避免 get_toc 默认深度截断或循环时返回部分结果。"""
    raw = pdfium.raw
    first = raw.FPDFBookmark_GetFirstChild(document, None)
    pending = [first] if first else []
    seen = set()
    result = []
    while pending:
        pointer = pending.pop()
        address = ctypes.addressof(pointer.contents)
        if address in seen:
            raise SourceError(SOURCE, "PDF 书签存在循环或重复引用")
        seen.add(address)
        bookmark = pdfium.PdfBookmark(pointer, document, 0)
        title = bookmark.get_title()
        if not isinstance(title, str):
            raise SourceError(SOURCE, "PDF 书签标题损坏")
        title.encode("utf-8", errors="strict")
        destination = bookmark.get_dest()
        index = None if destination is None else destination.get_index()
        if index is not None and (type(index) is not int or not 0 <= index < page_count):
            raise SourceError(SOURCE, "PDF 书签页面目标越界或损坏")
        result.append({"title": title, "page_number": None if index is None else index + 1})
        sibling = raw.FPDFBookmark_GetNextSibling(document, pointer)
        child = raw.FPDFBookmark_GetFirstChild(document, pointer)
        if sibling:
            pending.append(sibling)
        if child:
            pending.append(child)
    return result


def pdf_text(url: str, *, timeout: float) -> dict:
    """仅提取文字层与原生书签，任一解析失败均不返回部分内容。"""
    request_url = _request_url(url)
    # 可选模块初始化也在锁内；普通 FinchX 导入不加载 PDFium。
    with _PDFIUM_LOCK:
        try:
            pdfium = import_module("pypdfium2")
        except ImportError as exc:
            raise SourceError(SOURCE, 'PDF 提取需要安装可选依赖：pip install "finchx[pdf]"') from exc
        except Exception as exc:
            raise SourceError(SOURCE, f"PDF 依赖加载失败（{type(exc).__name__}）") from exc
    body = get_bytes(request_url, timeout=timeout,
                     headers={**DEFAULT_HEADERS, "Accept": "application/pdf, */*;q=0.8", "Accept-Encoding": "identity"},
                     source=SOURCE)
    if not isinstance(body, bytes) or not body:
        raise SourceError(SOURCE, "下载内容为空或不是有效的 PDF 字节")
    with _PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(body)
            try:
                page_count = len(document)
                if page_count < 1:
                    raise SourceError(SOURCE, "PDF 没有实际页面")
                outline = _outline(pdfium, document, page_count)
                pages = []
                has_text = False
                affected_pages = []
                for index in range(page_count):
                    page = document[index]
                    try:
                        textpage = page.get_textpage()
                        try:
                            recovered = False
                            try:
                                content = textpage.get_text_bounded(errors="strict")
                            except UnicodeDecodeError as exc:
                                encoding = exc.encoding.lower().replace("_", "-")
                                if encoding not in {"utf-16", "utf-16-le", "utf-16-be", "utf16", "utf16le", "utf16be"}:
                                    raise
                                # 不猜测 PDFium 未能完整表达的符号；保留其余文字并明确占位。
                                content = textpage.get_text_bounded(errors="replace")
                                recovered = True
                                affected_pages.append(index + 1)
                            if not isinstance(content, str):
                                raise SourceError(SOURCE, f"PDF 第 {index + 1} 页文字层损坏")
                            content = content.replace("\r\n", "\n").replace("\r", "\n")
                            readable_content = content.replace("�", "") if recovered else content
                            has_text = has_text or bool(readable_content.strip())
                            pages.append({"page_number": index + 1, "content": content})
                        finally:
                            textpage.close()
                    finally:
                        page.close()
                if not has_text:
                    raise SourceError(SOURCE, "PDF 全文没有非空白文字层，未执行 OCR")
            finally:
                document.close()
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(SOURCE, f"PDF 打开或解析失败（{type(exc).__name__}：{exc}）") from exc
    # 只有全部解析和 native 资源关闭成功后才提示；遵循标准警告过滤规则。
    if affected_pages:
        page_numbers = "、".join(map(str, affected_pages))
        warnings.warn(
            f"PDF 第 {page_numbers} 页的部分符号编码异常，已使用 � 占位；其余可提取文字已保留。",
            UserWarning,
            stacklevel=3,
        )
    return {"outline": outline, "pages": pages}
