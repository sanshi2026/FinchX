"""Taoguba authenticated activity-feed adapter for forum replies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from finchx.contracts import Source
from finchx.datasets.document_common import DescendingTimestampPages
from finchx.datasets.forum import ForumReply
from finchx.providers.errors import ProviderError
from finchx.providers.http import (
    DEFAULT_TIMEOUT_SECONDS,
    build_headers,
    call_with_transient_retries,
    http_status_failure_reason,
)


TAOGUBA_BASE_URL = "https://www.tgb.cn/"
TAOGUBA_REPLIES_ENDPOINT = urljoin(TAOGUBA_BASE_URL, "super/spefocus/friendActions")
TAOGUBA_FORUM_PROVIDER_ID = "taoguba.forum"
_PAGE_SIZE = 20
_MAX_PAGES = 50
_SOURCE_TIMEZONE = timezone(timedelta(hours=8))
_DATETIME = re.compile(
    r"(20[0-9]{2})[-/]([0-9]{1,2})[-/]([0-9]{1,2})\s+"
    r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?"
)
_QUOTE_PREFIX = re.compile(r"^引用\S+?说[：:]\s*")
_POST_TITLE_ACTIONS = {
    "原始链接",
    "查看原文",
    "定位原文",
    "original",
    "view original",
    "locate original",
}


def _normalize_cookies(cookies: str | Mapping[str, str]) -> str:
    if isinstance(cookies, str):
        value = cookies.strip()
        if not value:
            raise ValueError("cookies must be a non-empty string or mapping")
        return value
    if not isinstance(cookies, Mapping):
        raise TypeError("cookies must be a string or mapping")
    if not cookies:
        raise ValueError("cookies mapping must not be empty")
    parts: list[str] = []
    for name, value in cookies.items():
        if not isinstance(name, str) or not name.strip():
            raise TypeError("cookie names must be non-empty strings")
        if not isinstance(value, str):
            raise TypeError("cookie values must be strings")
        parts.append(f"{name.strip()}={value}")
    return "; ".join(parts)


@dataclass(frozen=True)
class _ForumHttpResponse:
    status_code: int
    text: str


class _ForumTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _ForumHttpResponse: ...


class _UrllibForumTransport:
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> _ForumHttpResponse:
        query = urlencode(params)
        request_url = f"{url}?{query}" if query else url
        request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return _ForumHttpResponse(int(response.status), body.decode(charset))
        except HTTPError as exc:
            return _ForumHttpResponse(int(exc.code), "")
        except (URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
            raise _ForumTransportFailure(type(exc).__name__) from exc


class _ForumTransportFailure(RuntimeError):
    pass


def _text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _quote_text(value: Any) -> str:
    text = _text(value)
    while True:
        stripped = _QUOTE_PREFIX.sub("", text)
        if stripped == text:
            return text
        text = stripped


def _parse_reply_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo and value.utcoffset() is not None else value.replace(tzinfo=_SOURCE_TIMEZONE)
    text = _text(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        match = _DATETIME.search(text)
        if match is None:
            raise ValueError("Taoguba actionDate is not a supported timestamp")
        year, month, day, hour, minute, second = match.groups()
        parsed = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second or 0),
            tzinfo=_SOURCE_TIMEZONE,
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_SOURCE_TIMEZONE)
    return parsed


def _field(record: Mapping[str, Any], name: str) -> str:
    return _text(record.get(name))


def _parse_record(
    record: Mapping[str, Any],
    *,
    captured_at: datetime,
    source: Source,
) -> ForumReply | None:
    # The legacy source documents actionName=R as the reply activity marker.
    # All other activity types are intentionally excluded before field mapping.
    if _field(record, "actionName") != "R":
        return None

    post_id = _field(record, "newTopicID")
    # actionID is the record's unique numeric reply/activity ID.  objectID
    # identifies the referenced forum object and may repeat for one thread.
    reply_id = _field(record, "actionID")
    username = _field(record, "userName")
    user_id = _field(record, "userID") or None
    reply_content = _field(record, "body")
    parent_username = _field(record, "quoteUserName")
    parent_content = _quote_text(record.get("quoteContent"))
    if not all((post_id, reply_id, username, reply_content, parent_username, parent_content)):
        return None
    if not reply_id.isdigit():
        return None
    if user_id is not None and not user_id.isdigit():
        return None

    try:
        reply_time = _parse_reply_time(record.get("actionDate"))
        post_title = _field(record, "objectName") or None
        if post_title and post_title.casefold() in _POST_TITLE_ACTIONS:
            post_title = None
        return ForumReply(
            replyId=reply_id,
            userId=user_id,
            username=username,
            replyTime=reply_time,
            replyContent=reply_content,
            parentUsername=parent_username,
            parentContent=parent_content,
            postId=post_id,
            postTitle=post_title,
            postUrl=urljoin(TAOGUBA_BASE_URL, f"a/{post_id}"),
            replyUrl=urljoin(TAOGUBA_BASE_URL, f"a/{post_id}/{reply_id}#{reply_id}"),
            source=Source(
                providerId=source.provider_id,
                sourceRecordId=reply_id,
                sourceUrl=TAOGUBA_REPLIES_ENDPOINT,
            ),
            capturedAt=captured_at,
        )
    except (TypeError, ValueError) as exc:
        raise ProviderError(source, f"invalid Taoguba reply record: {type(exc).__name__}") from exc


class TaogubaForumProvider:
    """Fetch qualified replies from Taoguba's authenticated following feed."""

    provider_id = TAOGUBA_FORUM_PROVIDER_ID

    def __init__(
        self,
        transport: _ForumTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = transport or _UrllibForumTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = timeout_seconds
        self._source = Source(providerId=self.provider_id, sourceUrl=TAOGUBA_REPLIES_ENDPOINT)

    @property
    def source(self) -> Source:
        return self._source

    def current_time(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _headers_for(self, cookies: str | Mapping[str, str]) -> dict[str, str]:
        return build_headers(
            accept="application/json, text/javascript, */*; q=0.01",
            referer=TAOGUBA_BASE_URL,
            extra={
                "Cookie": _normalize_cookies(cookies),
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    def _get_page(self, *, page_num: int, cookies: str | Mapping[str, str]) -> tuple[Mapping[str, Any], ...]:
        return call_with_transient_retries(
            lambda: self._get_page_once(page_num=page_num, cookies=cookies)
        )

    def _get_page_once(self, *, page_num: int, cookies: str | Mapping[str, str]) -> tuple[Mapping[str, Any], ...]:
        try:
            response = self._transport.get(
                TAOGUBA_REPLIES_ENDPOINT,
                params={"perPageNum": _PAGE_SIZE, "actionID": page_num * _PAGE_SIZE, "type": "A"},
                headers=self._headers_for(cookies),
                timeout_seconds=self._timeout_seconds,
            )
        except _ForumTransportFailure as exc:
            raise ProviderError(self._source, f"transport failed: {exc}") from exc
        reason = http_status_failure_reason(response.status_code)
        if reason is not None:
            raise ProviderError(self._source, reason)
        if not response.text.strip():
            raise ProviderError(self._source, "empty JSON response")
        try:
            payload = json.loads(response.text)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError(self._source, "Taoguba replies response is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ProviderError(self._source, "Taoguba replies response is not an object")
        dto = payload.get("dto")
        if dto is None or dto == {}:
            return ()
        if not isinstance(dto, Mapping):
            raise ProviderError(self._source, "Taoguba replies dto is not an object")
        records = dto.get("record")
        if records is None:
            # The real endpoint omits dto.record on the terminal page.
            return ()
        if not isinstance(records, list) or any(not isinstance(item, Mapping) for item in records):
            raise ProviderError(self._source, "Taoguba dto.record is not a list of objects")
        return tuple(records)

    def fetch_replies(
        self,
        *,
        user_names: tuple[str, ...] | None = None,
        max_results: int | None = None,
        since: date | datetime | None = None,
        until: date | datetime | None = None,
        cookies: str | Mapping[str, str],
    ) -> tuple[ForumReply, ...]:
        return self.fetch_replies_with_warnings(
            user_names=user_names,
            max_results=max_results,
            since=since,
            until=until,
            cookies=cookies,
        )[0]

    def fetch_replies_with_warnings(
        self,
        *,
        user_names: tuple[str, ...] | None = None,
        max_results: int | None = None,
        since: date | datetime | None = None,
        until: date | datetime | None = None,
        cookies: str | Mapping[str, str],
    ) -> tuple[tuple[ForumReply, ...], tuple[str, ...]]:
        captured_at = self.current_time()
        records: list[ForumReply] = []
        warnings: list[str] = []
        chronology = DescendingTimestampPages()
        for page_num in range(_MAX_PAGES):
            page = self._get_page(page_num=page_num, cookies=cookies)
            if not page:
                break
            parsed_page: list[ForumReply | None] = []
            for raw_record in page:
                record = _parse_record(raw_record, captured_at=captured_at, source=self._source)
                parsed_page.append(record)
                if record is None:
                    continue
                if user_names is not None and record.username not in user_names:
                    continue
                if not _in_datetime_range(record.reply_time, since=since, until=until):
                    continue
                records.append(record)
                if max_results is not None and len(records) >= max_results:
                    return tuple(records), tuple(warnings)
            if chronology.page_is_before_since(
                tuple(record.reply_time if record is not None else None for record in parsed_page),
                since,
            ):
                break
            # The endpoint may return a short page before older records are
            # exhausted.  Only an explicitly empty record list ends paging.
            if page_num + 1 == _MAX_PAGES:
                warnings.append(
                    f"Forum search stopped after {_MAX_PAGES} pages; additional replies may match the requested filters."
                )
        return tuple(records), tuple(warnings)


def _as_datetime(value: date | datetime | None, *, end: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("forum since/until datetimes must include a timezone offset")
        return value
    return datetime.combine(value, datetime.max.time() if end else datetime.min.time(), tzinfo=_SOURCE_TIMEZONE)


def _in_datetime_range(
    value: datetime | None,
    *,
    since: date | datetime | None,
    until: date | datetime | None,
) -> bool:
    if value is None:
        return since is None and until is None
    lower = _as_datetime(since)
    upper = _as_datetime(until, end=True)
    return (lower is None or value >= lower) and (upper is None or value <= upper)


__all__ = ["TAOGUBA_BASE_URL", "TAOGUBA_REPLIES_ENDPOINT", "TaogubaForumProvider"]
