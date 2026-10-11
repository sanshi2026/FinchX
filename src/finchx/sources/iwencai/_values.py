"""问财已核业务值的必要校验，不保存调用身份。"""

import json
import math
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlsplit

from finchx._common.errors import SourceError

SOURCE = "问财"
BEIJING = timezone(timedelta(hours=8))


def fail(reason):
    raise SourceError(SOURCE, reason)


def text(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        fail("业务文字类型无效")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        fail("业务文字含非法控制字符")
    try:
        value.encode("utf-8")
    except UnicodeError:
        fail("业务文字编码无效")
    result = value.strip()
    if not result and required:
        fail("必要业务文字缺失")
    return result or None


def query_text(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("query 必须为非空且不含控制字符的字符串")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("query 编码无效") from None
    return value


def limit_value(value, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or (maximum is not None and value > maximum):
        raise ValueError("limit 必须为范围内的非布尔正整数")
    return value


def credential(value, name):
    if not isinstance(value, str) or not value.strip() or not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{name} 必须为非空且合法的认证字符串")
    return value.strip()


def cookie_header(value):
    if isinstance(value, str):
        return credential(value, "cookies")
    if not isinstance(value, Mapping) or not value:
        raise ValueError("cookies 必须为非空字符串或字符串键值字典")
    pairs = []
    for key, item in value.items():
        if not isinstance(key, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
            raise ValueError("cookies 名称无效")
        if not isinstance(item, str) or not item.isascii() or any(ord(c) < 33 or ord(c) == 127 or c in ';,"\\' for c in item):
            raise ValueError("cookies 值无效")
        pairs.append(f"{key}={item}")
    return "; ".join(pairs)


def json_object(value):
    if isinstance(value, str):
        invalid = False
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            invalid = True
        if invalid:
            fail("来源 JSON 无效")
    if not isinstance(value, dict):
        fail("来源必要对象结构损坏")
    return value


def status(document, *, required=True):
    fields = ("status_code", "statusCode", "error_code", "errorCode", "errorcode")
    present = [document[key] for key in fields if key in document]
    if any(not (type(v) is int and v == 0 or type(v) is str and v == "0") for v in present):
        fail("来源拒绝请求或认证失效")
    if "success" in document and document["success"] is not True:
        fail("来源拒绝请求或认证失效")
    if required and not present and document.get("success") is not True:
        fail("来源成功状态缺失")


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        fail("来源数值类型无效")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        fail("来源数值无效")
    if not math.isfinite(result):
        fail("来源数值不是有限值")
    return result


def source_time(value):
    value = text(value)
    if value is None:
        return None
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return date.fromisoformat(value).isoformat()
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?", value):
            moment = datetime(
                int(value[:4]), int(value[5:7]), int(value[8:10]),
                int(value[11:13]), int(value[14:16]), int(value[17:19]) if len(value) == 19 else 0,
                tzinfo=BEIJING,
            )
            return moment.isoformat(timespec="seconds" if len(value) == 19 else "minutes")
    except ValueError:
        pass
    fail("来源日期或时刻无效")


def business_url(value):
    value = text(value)
    if value is None:
        return None
    try:
        parts = urlsplit(value)
        valid = parts.scheme in ("http", "https") and parts.hostname and parts.username is None and parts.password is None
        parts.port
    except ValueError:
        valid = False
    if not valid or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value):
        fail("来源业务链接无效")
    return value
