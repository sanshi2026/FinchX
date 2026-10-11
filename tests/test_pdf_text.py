"""离线 PDF 协议、资源与真实 PDFium 提取回归；不代替联网样本。"""

from concurrent.futures import ThreadPoolExecutor
import ctypes
from http.client import IncompleteRead
from io import BytesIO
import os
import subprocess
import sys
from threading import Barrier, Lock
import time
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult
import warnings

import pytest

from finchx import FinchX, SourceError
from finchx._common import http, pdf


@pytest.mark.parametrize("value", [None, 123, True, b"https://example.org/a", "", "file:///a.pdf",
    "//example.org/a.pdf", "https:///a", "https://u:p@example.org/a", "https://@example.org/a",
    "https://example.org:", "https://example.org:0/a", "https://example.org:65536/a",
    "https://example.org:abc/a", "https://[::1]x/a", "https://example.org/a b",
    " https://example.org/a", "https://example.org/a\n", "https://example.org/\t",
    "https://example.org/a\\b", "https://example.org/\x7f", "https://example.org/\x85",
    "https://example.org/\ud800", "https://[invalid]/a"])
def test_invalid_url_fails_before_import_or_network(monkeypatch, value):
    monkeypatch.setattr(pdf, "import_module", lambda *a: pytest.fail("不应加载依赖"))
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: pytest.fail("不应下载"))
    with pytest.raises(ValueError, match="url"):
        FinchX().reference.pdf_text(value)


@pytest.mark.parametrize("value", ["https://unknown.example/download?id=123&signature=a%2Fb+c==",
    "http://localhost:8080/file", "https://[::1]:443/file?key=0", "HTTPS://example.org/file?x=/a?b%20c"])
def test_url_keeps_legal_query_and_ports(value):
    assert pdf._request_url(value) == value.replace("HTTPS://", "https://")


@pytest.mark.parametrize("authority", ["[invalid]", "[127.0.0.1]", "[::gg]", "[v1.]", "[vQ.future]",
    "[V1.future]", "prefix[::1]", "[::1]suffix", "[::1]:80:90", "[invalid]:8080"])
def test_bracketed_host_validation_without_urlsplit_checks(monkeypatch, authority):
    # 早期 Python 3.10 的 urlsplit 不验证方括号内容；模拟其返回值。
    monkeypatch.setattr(pdf, "urlsplit", lambda value: SplitResult("https", authority, "/a", "source=0", ""))
    monkeypatch.setattr(pdf, "import_module", lambda *a: pytest.fail("不应加载依赖"))
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: pytest.fail("不应下载"))
    with pytest.raises(ValueError, match="url"):
        FinchX().reference.pdf_text(f"https://{authority}/a?source=0")


@pytest.mark.parametrize("authority", ["[::1]", "[2001:db8::1]:443", "[::ffff:192.0.2.1]:08080",
    "[v1.future]", "[vf.future]:8080", "[v1.a:b]:443"])
def test_legal_bracketed_hosts_without_urlsplit_checks(monkeypatch, authority):
    monkeypatch.setattr(pdf, "urlsplit", lambda value: SplitResult("https", authority, "/a", "source=0", ""))
    url = f"https://{authority}/a?source=0"
    assert pdf._request_url(url) == url


def test_unicode_url_encodes_only_for_transport():
    assert pdf._request_url("https://例子.中国/公告?名称=原文&sig=a%2Fb+c==") == (
        "https://xn--fsqu00a.xn--fiqs8s/%E5%85%AC%E5%91%8A?%E5%90%8D%E7%A7%B0="
        "%E5%8E%9F%E6%96%87&sig=a%2Fb+c==")


def test_unicode_host_and_explicit_port_are_encoded_independently():
    assert pdf._request_url("https://例子.公司:08080/文档.pdf?sig=a%2Fb+c==") == (
        "https://xn--fsqu00a.xn--55qx5d:08080/%E6%96%87%E6%A1%A3.pdf?sig=a%2Fb+c==")


class Response:
    def __init__(self, body=b"%PDF-bytes", status=200, headers=None, error=None):
        self.body, self.status, self.headers, self.error = body, status, headers or {}, error
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self):
        if self.error:
            raise self.error
        return self.body


def test_get_bytes_preserves_bytes_headers_and_timeout(monkeypatch):
    response = Response(b"\x00\xff%PDF\r\n", headers={"Content-Length": "8"})
    calls = []
    monkeypatch.setattr(http, "urlopen", lambda request, **kwargs: calls.append((request, kwargs)) or response)
    headers = {"Accept": "application/pdf"}
    assert http.get_bytes("https://example.org/file?q=a%2Bb", timeout=2.5, headers=headers, source="pdf") == response.body
    assert calls[0][0].full_url == "https://example.org/file?q=a%2Bb"
    assert calls[0][0].get_method() == "GET"
    assert calls[0][1] == {"timeout": 2.5}
    assert headers == {"Accept": "application/pdf"} and response.closed


@pytest.mark.parametrize("response", [Response(status=403), Response(status=206),
    Response(headers={"Content-Length": "999"}), Response(headers={"Content-Length": "-1"}),
    Response(headers={"Content-Length": "１"}), Response(headers={"Content-Length": "unknown"}),
    Response(body="not bytes"), Response(error=IncompleteRead(b"%PDF", 30)), Response(error=TimeoutError())])
def test_get_bytes_rejects_failed_or_incomplete_response(monkeypatch, response):
    monkeypatch.setattr(http, "urlopen", lambda *a, **k: response)
    with pytest.raises(SourceError) as caught:
        http.get_bytes("https://example.org/file", timeout=1, headers={}, source="pdf")
    assert caught.value.source == "pdf" and response.closed
    if response.error:
        assert caught.value.__cause__ is response.error


@pytest.mark.parametrize("error", [HTTPError("https://example.org/file", 503, "", {}, None), URLError("offline")])
def test_get_bytes_wraps_open_failures(monkeypatch, error):
    def fail(*a, **k):
        raise error
    monkeypatch.setattr(http, "urlopen", fail)
    with pytest.raises(SourceError) as caught:
        http.get_bytes("https://example.org/file", timeout=1, headers={}, source="pdf")
    assert caught.value.__cause__ is error


def test_missing_optional_dependency_and_top_level_lazy_import(monkeypatch):
    def unavailable(name):
        assert name == "pypdfium2"
        raise ImportError("missing")
    monkeypatch.setattr(pdf, "import_module", unavailable)
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: pytest.fail("不应下载"))
    with pytest.raises(SourceError, match=r"finchx\[pdf\]"):
        FinchX().reference.pdf_text("https://example.org/a")
    subprocess.run([sys.executable, "-c", "import sys; import finchx; assert 'pypdfium2' not in sys.modules"],
                   check=True, env={**os.environ, "PYTHONPATH": "src"})


def install_reader(monkeypatch, *, texts=None, bookmarks=None, defect=None):
    """可控原生句柄替身仅用于失败/关闭/并发场景，非真实来源返回。"""
    texts = ["正文"] if texts is None else texts
    bookmarks = [] if bookmarks is None else bookmarks
    events, requests = [], []
    pointers = [ctypes.pointer(ctypes.c_int(i)) for i in range(len(bookmarks))]
    identities = {ctypes.addressof(p.contents): i for i, p in enumerate(pointers)}

    class TextPage:
        def __init__(self, index): self.index = index
        def get_text_bounded(self, **kwargs):
            assert kwargs["errors"] in {"strict", "replace"}
            if defect == "text" and self.index == len(texts) - 1:
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "broken")
            if defect == "fallback" and kwargs["errors"] == "replace":
                raise RuntimeError("fallback failed")
            value = texts[self.index]
            if isinstance(value, bytes):
                events.append(("decode", self.index, kwargs["errors"]))
                return value.decode("utf-16-le", errors=kwargs["errors"])
            return value
        def close(self):
            events.append(("text_close", self.index))
            if defect == "text_close": raise RuntimeError("text close failed")

    class Page:
        def __init__(self, index): self.index = index
        def get_textpage(self):
            if defect == "textpage" and self.index == len(texts) - 1: raise RuntimeError("textpage failed")
            return TextPage(self.index)
        def close(self):
            events.append(("page_close", self.index))
            if defect == "page_close": raise RuntimeError("page close failed")

    class Document:
        def __init__(self, body):
            assert body == b"%PDF test"
            if defect == "open": raise RuntimeError("open failed")
            events.append(("open", None))
        def __len__(self): return len(texts)
        def __getitem__(self, index):
            if defect == "page" and index == len(texts) - 1: raise RuntimeError("page failed")
            return Page(index)
        def close(self):
            events.append(("doc_close", None))
            if defect == "doc_close": raise RuntimeError("doc close failed")

    class Bookmark:
        def __init__(self, pointer, document, level): self.index = identities[ctypes.addressof(pointer.contents)]
        def get_title(self):
            if defect == "bookmark": raise RuntimeError("bookmark failed")
            return bookmarks[self.index]["title"]
        def get_dest(self):
            entry = bookmarks[self.index]
            return None if entry.get("no_dest") else SimpleNamespace(get_index=lambda: entry.get("page"))

    def first(document, pointer):
        if pointer is None:
            return pointers[0] if pointers else None
        child = bookmarks[identities[ctypes.addressof(pointer.contents)]].get("child")
        return pointers[child] if child is not None else None

    def sibling(document, pointer):
        next_index = bookmarks[identities[ctypes.addressof(pointer.contents)]].get("next")
        return pointers[next_index] if next_index is not None else None

    module = SimpleNamespace(PdfDocument=Document, PdfBookmark=Bookmark,
        raw=SimpleNamespace(FPDFBookmark_GetFirstChild=first, FPDFBookmark_GetNextSibling=sibling))
    monkeypatch.setattr(pdf, "import_module", lambda name: module)
    monkeypatch.setattr(pdf, "get_bytes", lambda url, **kw: requests.append((url, kw)) or b"%PDF test")
    return module, events, requests


def test_full_contract_unicode_blank_pages_outline_order_and_timeout(monkeypatch):
    _, events, requests = install_reader(monkeypatch,
        texts=["  首页😀\r\n中间\r末尾  ", "", "附录\n"],
        bookmarks=[{"title": "第一章", "page": 0, "child": 1, "next": 2},
                   {"title": "子节😀", "page": 2}, {"title": "原生外链", "no_dest": True}])
    result = FinchX(timeout=2.5).reference.pdf_text("https://example.org/file?sig=a%2Fb+c==")
    assert result == {"outline": [{"title": "第一章", "page_number": 1},
        {"title": "子节😀", "page_number": 3}, {"title": "原生外链", "page_number": None}],
        "pages": [{"page_number": 1, "content": "  首页😀\n中间\n末尾  "},
                  {"page_number": 2, "content": ""}, {"page_number": 3, "content": "附录\n"}]}
    assert events == [("open", None), ("text_close", 0), ("page_close", 0),
        ("text_close", 1), ("page_close", 1), ("text_close", 2), ("page_close", 2), ("doc_close", None)]
    assert requests[0][0] == "https://example.org/file?sig=a%2Fb+c=="
    assert requests[0][1]["timeout"] == 2.5


@pytest.mark.parametrize("texts", [[], [""], [" \r\n\t", ""]])
def test_all_empty_or_whitespace_document_fails_and_closes(monkeypatch, texts):
    _, events, _ = install_reader(monkeypatch, texts=texts)
    with pytest.raises(SourceError): FinchX().reference.pdf_text("https://example.org/file")
    assert events[-1] == ("doc_close", None)


@pytest.mark.parametrize("defect", ["open", "page", "textpage", "text", "bookmark"])
def test_mid_parse_failure_never_returns_partial_and_closes_handles(monkeypatch, defect):
    _, events, _ = install_reader(monkeypatch, texts=["有效第一页", "坏末页"],
                                 bookmarks=[{"title": "书签", "page": 0}], defect=defect)
    with pytest.raises(SourceError) as caught: FinchX().reference.pdf_text("https://example.org/file")
    assert isinstance(caught.value.__cause__, Exception)
    if defect == "open":
        assert events == []
    else:
        assert events[-1] == ("doc_close", None)
    if defect == "text":
        assert events[-3:] == [("text_close", 1), ("page_close", 1), ("doc_close", None)]
    if defect == "textpage": assert ("page_close", 1) in events


@pytest.mark.parametrize("defect", ["text_close", "page_close", "doc_close"])
def test_close_failure_is_explicit_and_still_closes_parent(monkeypatch, defect):
    _, events, _ = install_reader(monkeypatch, defect=defect)
    with pytest.raises(SourceError): FinchX().reference.pdf_text("https://example.org/file")
    assert events[-1] == ("doc_close", None)
    assert ("page_close", 0) in events and ("text_close", 0) in events


def test_utf16_fallback_preserves_text_and_summarizes_pages_once_after_close(monkeypatch):
    high = "  中文𝐹😀\r\n".encode("utf-16-le") + b"\x35\xd8" + "末尾  ".encode("utf-16-le")
    low = "有效𝑚".encode("utf-16-le") + b"\x35\xdc" + "\r保留".encode("utf-16-le")
    _, events, _ = install_reader(monkeypatch, texts=[high, "", low])
    with pytest.warns(UserWarning, match="第 1、3 页.*�") as emitted:
        result = FinchX().reference.pdf_text("https://example.org/file")
    assert len(emitted) == 1 and emitted[0].filename == __file__
    assert result == {"outline": [], "pages": [
        {"page_number": 1, "content": "  中文𝐹😀\n�末尾  "},
        {"page_number": 2, "content": ""}, {"page_number": 3, "content": "有效𝑚�\n保留"}]}
    assert events[-1] == ("doc_close", None)
    assert [e for e in events if e[0] == "decode"] == [
        ("decode", 0, "strict"), ("decode", 0, "replace"),
        ("decode", 2, "strict"), ("decode", 2, "replace")]
    result["pages"][0]["content"].encode("utf-8", errors="strict")


@pytest.mark.parametrize("defect", ["fallback", "text", "doc_close"])
def test_fallback_or_later_failure_has_no_success_warning(monkeypatch, defect):
    encoded = "正文".encode("utf-16-le") + b"\x35\xd8"
    _, events, _ = install_reader(monkeypatch, texts=[encoded, "末页"], defect=defect)
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(SourceError): FinchX().reference.pdf_text("https://example.org/file")
    assert emitted == [] and events[-1] == ("doc_close", None)
    if defect == "text":
        assert ("decode", 0, "replace") in events
        assert ("decode", 1, "replace") not in events


@pytest.mark.parametrize("policy", ["ignore", "error"])
def test_recovery_warning_respects_filter_and_is_not_source_error(monkeypatch, policy):
    _, events, _ = install_reader(monkeypatch, texts=["正文".encode("utf-16-le") + b"\x35\xd8"])
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter(policy, UserWarning)
        if policy == "error":
            with pytest.raises(UserWarning, match="第 1 页"):
                FinchX().reference.pdf_text("https://example.org/file")
        else:
            assert FinchX().reference.pdf_text("https://example.org/file")["pages"][0]["content"] == "正文�"
        assert emitted == []
    assert events[-1] == ("doc_close", None)


def test_normal_non_bmp_text_has_no_warning_and_no_fallback(monkeypatch):
    _, events, _ = install_reader(monkeypatch, texts=["中😀𝐹𝑚".encode("utf-16-le")])
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        assert FinchX().reference.pdf_text("https://example.org/file")["pages"][0]["content"] == "中😀𝐹𝑚"
    assert emitted == []
    assert [e for e in events if e[0] == "decode"] == [("decode", 0, "strict")]


def test_recovered_placeholders_alone_do_not_make_a_readable_document(monkeypatch):
    _, events, _ = install_reader(monkeypatch, texts=[b"\x35\xd8", b"\x35\xdc" + " \r\n".encode("utf-16-le")])
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(SourceError, match="没有非空白文字层"):
            FinchX().reference.pdf_text("https://example.org/file")
    assert emitted == [] and events[-1] == ("doc_close", None)


def test_source_literal_replacement_character_on_strict_page_is_unchanged(monkeypatch):
    install_reader(monkeypatch, texts=["�"])
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        assert FinchX().reference.pdf_text("https://example.org/file")["pages"] == [
            {"page_number": 1, "content": "�"}]
    assert emitted == []


@pytest.mark.parametrize("index", [-1, 1, True, 1.0, "0"])
def test_invalid_bookmark_page_fails_whole_document(monkeypatch, index):
    _, events, _ = install_reader(monkeypatch, bookmarks=[{"title": "书签", "page": index}])
    with pytest.raises(SourceError, match="书签"): FinchX().reference.pdf_text("https://example.org/file")
    assert events[-1] == ("doc_close", None)


def test_none_destination_index_is_preserved(monkeypatch):
    install_reader(monkeypatch, bookmarks=[{"title": "未指向页面", "page": None}])
    assert FinchX().reference.pdf_text("https://example.org/file")["outline"] == [
        {"title": "未指向页面", "page_number": None}]


def test_deep_outline_is_complete_and_circular_outline_fails(monkeypatch):
    rows = [{"title": str(i), "page": 0, "child": i + 1} for i in range(1200)]
    rows[-1].pop("child")
    install_reader(monkeypatch, bookmarks=rows)
    assert len(FinchX().reference.pdf_text("https://example.org/file")["outline"]) == 1200
    rows[-1]["child"] = 0
    _, events, _ = install_reader(monkeypatch, bookmarks=rows)
    with pytest.raises(SourceError, match="循环"): FinchX().reference.pdf_text("https://example.org/file")
    assert events[-1] == ("doc_close", None)


def test_two_calls_download_concurrently_but_pdfium_and_close_are_serial(monkeypatch):
    module, events, _ = install_reader(monkeypatch)
    downloads = Barrier(2)
    state_lock = Lock()
    active = 0
    original_document = module.PdfDocument
    class CheckedDocument(original_document):
        def __init__(self, body):
            nonlocal active
            with state_lock:
                active += 1
                assert active == 1
            super().__init__(body)
            time.sleep(0.01)
        def close(self):
            nonlocal active
            super().close()
            with state_lock:
                assert active == 1
                active -= 1
    module.PdfDocument = CheckedDocument
    def download(*args, **kwargs):
        downloads.wait(timeout=3)
        return b"%PDF test"
    monkeypatch.setattr(pdf, "get_bytes", download)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(FinchX().reference.pdf_text, ["https://example.org/a", "https://example.org/b"]))
    assert results[0] == results[1] and active == 0
    assert [e for e in events if e[0] in {"open", "doc_close"}] == [
        ("open", None), ("doc_close", None), ("open", None), ("doc_close", None)]


def test_real_pdfium_generated_pdf_with_empty_page(monkeypatch):
    """由已安装 PDFium 生成的小 PDF；仅离线真实解析，不是来源成功样本。"""
    pdfium = pytest.importorskip("pypdfium2")
    buffer = BytesIO()
    with pdfium.PdfDocument.new() as document:
        page = document.new_page(300, 200)
        text = pdfium.raw.FPDFPageObj_NewTextObj(document, b"Helvetica", 12)
        encoded = ctypes.create_string_buffer("PDFium text layer".encode("utf-16-le") + b"\x00\x00")
        assert pdfium.raw.FPDFText_SetText(text, ctypes.cast(encoded, pdfium.raw.FPDF_WIDESTRING))
        pdfium.raw.FPDFPageObj_Transform(text, 1, 0, 0, 1, 20, 100)
        pdfium.raw.FPDFPage_InsertObject(page, text)
        assert pdfium.raw.FPDFPage_GenerateContent(page)
        page.close()
        document.new_page(300, 200).close()
        document.save(buffer)
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: buffer.getvalue())
    assert FinchX().reference.pdf_text("https://example.org/download") == {
        "outline": [], "pages": [{"page_number": 1, "content": "PDFium text layer"},
                                  {"page_number": 2, "content": ""}]}


@pytest.mark.parametrize("body", [b"", b"<html>login</html>", b"%PDF-1.7\ncorrupt content"])
def test_actual_empty_non_pdf_or_broken_download_fails(monkeypatch, body):
    pytest.importorskip("pypdfium2")
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: body)
    with pytest.raises(SourceError): FinchX().reference.pdf_text("https://example.org/file")


def unicode_pdf_bytes(destination, unicode_target=b"D83DDE00"):
    """小型合成 PDF 的真实文字映射，不从来源或显示字形猜 Unicode。"""
    pdfium = pytest.importorskip("pypdfium2")
    cmap = b"""/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /CustomUnicode def /CMapType 2 def
1 begincodespacerange <0000> <FFFF> endcodespacerange
2 beginbfchar <0001> <4E2D> <0002> <D83DDE00> endbfchar
endcmap CMapName currentdict /CMap defineresource pop end end"""
    content = b"BT /F1 12 Tf 20 100 Td <00010002> Tj ET"
    if unicode_target != b"D83DDE00":
        cmap = cmap.replace(b"2 beginbfchar", b"3 beginbfchar").replace(
            b"<0002> <D83DDE00>", b"<0002> <" + unicode_target + b"> <0003> <D83DDE00>")
        content = b"BT /F1 12 Tf 20 100 Td <000100020003> Tj ET"
    def stream(value):
        return b"<< /Length " + str(len(value)).encode() + b" >>\nstream\n" + value + b"\nendstream"
    title = (b"\xfe\xff" + "原生😀".encode("utf-16-be")).hex().encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R /Outlines 9 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 8 0 R >>",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /TestFont /Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 7 0 R >>",
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /TestFont /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 6 0 R /DW 1000 >>",
        b"<< /Type /FontDescriptor /FontName /TestFont /Flags 4 /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 900 /Descent -100 /CapHeight 700 /StemV 80 >>",
        stream(cmap), stream(content),
        b"<< /Type /Outlines /First 10 0 R /Last 11 0 R /Count 2 >>",
        b"<< /Title <" + title + b"> /Parent 9 0 R /Next 11 0 R " + destination + b" >>",
        b"<< /Title (Native link) /Parent 9 0 R /Prev 10 0 R /A << /S /URI /URI (https://example.org/) >> >>",
    ]
    body, offsets = b"%PDF-1.7\n", [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 12\n0000000000 65535 f \n" + b"".join(
        f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    body += b"trailer\n<< /Root 1 0 R /Size 12 >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    # 先由 PDFium 保存后再走 SDK，验证实际库生成字节的 Unicode 与书签契约。
    buffer = BytesIO()
    with pdfium.PdfDocument(body) as document:
        document.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("destination", [b"/Dest [3 0 R /Fit]", b"/A << /S /GoTo /D [3 0 R /Fit] >>"])
def test_real_unicode_pdf_and_native_bookmarks(monkeypatch, destination):
    body = unicode_pdf_bytes(destination)
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: body)
    assert FinchX().reference.pdf_text("https://example.org/file") == {
        "outline": [{"title": "原生😀", "page_number": 1}, {"title": "Native link", "page_number": None}],
        "pages": [{"page_number": 1, "content": "中😀"}]}


@pytest.mark.parametrize("unicode_target", [b"D835", b"DC35"])
def test_real_isolated_surrogate_pdf_recovers_valid_non_bmp_and_body(monkeypatch, unicode_target):
    body = unicode_pdf_bytes(b"/Dest [3 0 R /Fit]", unicode_target)
    monkeypatch.setattr(pdf, "get_bytes", lambda *a, **k: body)
    with pytest.warns(UserWarning, match="第 1 页.*�") as emitted:
        result = FinchX().reference.pdf_text("https://example.org/file")
    assert len(emitted) == 1
    assert result == {
        "outline": [{"title": "原生😀", "page_number": 1}, {"title": "Native link", "page_number": None}],
        "pages": [{"page_number": 1, "content": "中�😀"}]}
