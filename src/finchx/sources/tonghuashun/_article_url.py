"""同花顺已核文章链接及同 ID 编码转换。"""

from datetime import date
from html import unescape
from hashlib import md5
import re
from urllib.parse import parse_qs, urlsplit

_NEWS_HOSTS = frozenset({"news.10jqka.com.cn", "stock.10jqka.com.cn", "fund.10jqka.com.cn", "fe.10jqka.com.cn", "goodsfu.10jqka.com.cn", "invest.10jqka.com.cn", "field.10jqka.com.cn"})
_EXTENDED = _NEWS_HOSTS - {"news.10jqka.com.cn", "stock.10jqka.com.cn"}
_MODULUS = 100_000_000_000
_MULTIPLIER = 2_147_483_647


def encode_news_seq(seq: str) -> str:
    if not isinstance(seq, str) or not re.fullmatch(r"[0-9]{6,16}", seq) or seq.startswith("0"):
        raise ValueError("新闻 ID 须为合法 ASCII 数字字符串")
    checksum = str(sum(map(int, seq)) % 10)
    digest = md5((seq + checksum).encode("ascii")).hexdigest()
    return digest[:4] + str(int(seq) * _MULTIPLIER % _MODULUS).zfill(11) + checksum + digest[-3:]


def decode_encoded_seq(encoded: str) -> str:
    """只还原已核可逆 ID，并以完整校验码复核，不能猜测截断 ID。"""
    if not isinstance(encoded, str) or not re.fullmatch(r"[a-f0-9]{4}[0-9]{12}[a-f0-9]{3}", encoded):
        raise ValueError("encoded 新闻链接格式无效")
    seq = str(int(encoded[4:15]) * pow(_MULTIPLIER, -1, _MODULUS) % _MODULUS)
    if len(seq) < 6 or encode_news_seq(seq) != encoded:
        raise ValueError("encoded 新闻身份校验失败")
    return seq


def classify_article_url(url: str) -> tuple[str, str, str, date | None]:
    if not isinstance(url, str) or not url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("url 须为无空白或控制字符的同花顺文章 URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("文章 URL 无效") from exc
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None or port not in (None, 443 if parsed.scheme == "https" else 80):
        raise ValueError("文章 URL 须为无认证信息的 HTTP(S) 地址")
    if host == "news.10jqka.com.cn":
        encoded = re.fullmatch(r"/mobile/news/article/v1/encoded/([a-f0-9]{4}[0-9]{12}[a-f0-9]{3})", parsed.path)
        if encoded:
            seq = decode_encoded_seq(encoded[1])
            return "news", f"https://{host}{parsed.path}", seq, None
        deep = re.fullmatch(r"/deep-topic/topic/(dt_[0-9A-Z]{26})", parsed.path)
        if deep and parsed.scheme == "https" and not parsed.query:
            return "topic_deep", f"https://{host}{parsed.path}", deep[1], None
    if host in _NEWS_HOSTS:
        match = re.fullmatch(r"/([0-9]{8})/c([0-9]{6,20})\.shtml", parsed.path, re.I)
        if match and not match[2].startswith("0"):
            if host in _EXTENDED and (parsed.scheme != "https" or parsed.query or len(match[2]) > 16 or parsed.path != f"/{match[1]}/c{match[2]}.shtml"):
                raise ValueError("扩展新闻频道仅支持已核 HTTPS 文章路径")
            try:
                day = date(int(match[1][:4]), int(match[1][4:6]), int(match[1][6:]))
            except ValueError as exc:
                raise ValueError("新闻 URL 日期无效") from exc
            return "news", f"https://{host}/{match[1]}/c{match[2]}.shtml", match[2], day
    if host == "t.10jqka.com.cn":
        if parsed.path == "/lgt/short_view/index.html" and parsed.scheme == "https":
            query = parse_qs(parsed.query, keep_blank_values=True)
            pid = query.get("pid", [])
            if set(query) == {"pid"} and len(pid) == 1 and re.fullmatch(r"[1-9][0-9]{5,19}", pid[0]):
                return "article_short", f"https://{host}{parsed.path}?pid={pid[0]}", pid[0], None
        match = re.fullmatch(r"/(?:m/zhibo/)?pid_([0-9]{6,20})\.shtml", parsed.path, re.I)
        if match and not match[1].startswith("0"):
            return "article", f"https://{host}{parsed.path}", match[1], None
        if parsed.path in {"/m/post/articleShare/articleshare.html", "/lgt/share_page/articleShare.html"} and parsed.scheme == "https":
            query = parse_qs(unescape(parsed.query), keep_blank_values=True)
            pid = query.get("pid", [])
            if (set(query) <= {"pid", "type"} and len(pid) == 1 and re.fullmatch(r"[1-9][0-9]{5,19}", pid[0]) and ("type" not in query or query["type"] == ["circle"])):
                return "article", f"https://{host}{parsed.path}?{parsed.query}", pid[0], None
    if host == "mams.10jqka.com.cn" and parsed.scheme == "https":
        match = re.fullmatch(r"/new/server/html/([1-9][0-9]{0,9})\.html", parsed.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if match and set(query) <= {"injectAdaptive"} and ("injectAdaptive" not in query or query["injectAdaptive"] in (["true"], ["false"])):
            return "topic_mams", f"https://{host}{parsed.path}" + (f"?{parsed.query}" if parsed.query else ""), match[1], None
    raise ValueError("不支持该同花顺文章链接")
