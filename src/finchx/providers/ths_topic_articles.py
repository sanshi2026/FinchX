"""Bounded article-reference discovery from Tonghuashun T-code topic feeds."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from finchx.contracts import Source
from finchx.datasets.topic_articles import TopicArticlesRequest
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason
from finchx.providers.ths_articles import encode_news_seq


TOPIC_RECOMMEND_URL = "https://t.10jqka.com.cn/lgt/topic/open/api/topic_info/v3/recommend_list"
TOPIC_PROVIDER_ID = "tonghuashun.topic"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SHARE_PATH = re.compile(r"^/mobile/news/article/v1/encoded/([A-Za-z0-9]+)$")
_PAGE_SIZE = 15
_MAX_API_PAGES = 8
_MAX_RESPONSE_BYTES = 4_000_000


class THSTopicArticlesProvider:
    """Provider for mixed T-code feeds, exposing only verified news refs."""

    provider_id = TOPIC_PROVIDER_ID

    def __init__(self, opener: Callable[..., Any] | None = None, *, clock=None) -> None:
        self._open = opener or urlopen
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId=self.provider_id, sourceUrl=TOPIC_RECOMMEND_URL)

    @property
    def source(self) -> Source:
        return self._source

    def fetch_raw_topic_articles(self, request: TopicArticlesRequest) -> dict[str, object]:
        if not isinstance(request, TopicArticlesRequest):
            raise ValueError("request must be a TopicArticlesRequest")

        rows: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        skipped_types: Counter[str] = Counter()
        skipped_invalid_items: Counter[str] = Counter()
        warnings: list[str] = []
        pages_used = 0
        skipped_malformed_items = 0
        query_type = "recommend"
        page = 1
        source_url = TOPIC_RECOMMEND_URL
        scan_exhausted = False
        stop = False

        while pages_used < _MAX_API_PAGES and not stop:
            params = {
                "code": request.topic_code,
                "page": str(page),
                "pageSize": str(_PAGE_SIZE),
                "queryType": query_type,
            }
            source_url = f"{TOPIC_RECOMMEND_URL}?{urlencode(params)}"
            payload = self._json_get(source_url)
            data = payload.get("data")
            if not isinstance(data, Mapping):
                self._fail("topic feed response did not contain an object data field")
            key = "list_recommend" if query_type == "recommend" else "list_feed"
            source_items = data.get(key)
            has_next = data.get("has_next")
            if not isinstance(source_items, list) or type(has_next) is not bool:
                self._fail(f"topic feed response did not contain {key} and boolean has_next")
            pages_used += 1

            for source_item in source_items:
                if not isinstance(source_item, Mapping):
                    skipped_malformed_items += 1
                    continue
                info = source_item.get("info")
                if not isinstance(info, Mapping):
                    skipped_malformed_items += 1
                    continue
                raw_type = info.get("type")
                item_type = str(raw_type) if raw_type is not None else "unknown"
                if item_type not in {"8", "2"}:
                    skipped_types[item_type] += 1
                    continue

                if item_type == "8":
                    item = self._news_row(request.topic_code, source_item, info, len(rows) + 1)
                    public_type = "news"
                else:
                    item = self._long_article_row(request.topic_code, source_item, info, len(rows) + 1)
                    public_type = "zhibo"
                if item is None:
                    skipped_invalid_items[item_type] += 1
                    continue
                item_data = item["data"]
                content_id = str(item_data["contentId"])
                identity = f"{public_type}:{content_id}"
                if identity in seen_ids:
                    continue
                seen_ids.add(identity)
                if len(rows) < request.limit:
                    rows.append({**item, "sourceUrl": source_url})
                else:
                    stop = True
            if stop or len(rows) >= request.limit:
                break

            if has_next:
                page += 1
                continue
            if query_type == "recommend":
                # The site's 综合 tab falls through to queryType=feed once its
                # recommendation segment is exhausted.
                query_type = "feed"
                page = 1
                continue
            break
        else:
            scan_exhausted = True

        if skipped_types:
            values = ", ".join(
                f"type {content_type}: {count}"
                for content_type, count in sorted(skipped_types.items(), key=lambda item: (not item[0].isdigit(), int(item[0]) if item[0].isdigit() else item[0]))
            )
            warnings.append(
                "Only verified type=8 news and type=2 long articles are included; skipped mixed-feed items "
                f"({values}). Type 18 express news and other content types are not exposed until their article-detail route is verified."
            )
        for item_type, count in sorted(skipped_invalid_items.items()):
            criteria = (
                "numeric ID, verified encoded share URL, title, or source timestamp"
                if item_type == "8"
                else "numeric ID, title, or source timestamp"
            )
            warnings.append(f"Skipped {count} type={item_type} feed items without a valid {criteria}.")
        if skipped_malformed_items:
            warnings.append(f"Skipped {skipped_malformed_items} malformed feed rows without an info object.")
        if scan_exhausted:
            warnings.append(
                f"The topic scan stopped at its {_MAX_API_PAGES}-page safety bound before confirming that more pages were exhausted."
            )
        partial_detail = " ".join(warnings)
        captured_at = self._clock()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            self._fail("provider clock must return a timezone-aware datetime")
        return {
            "rows": rows,
            "warnings": warnings,
            "partialDetail": partial_detail,
            "capturedAt": captured_at,
            "sourceUrl": source_url,
        }

    def _news_row(
        self,
        topic_code: str,
        source_item: Mapping[str, Any],
        info: Mapping[str, Any],
        rank: int,
    ) -> dict[str, object] | None:
        content_id = str(info.get("id") or "")
        if not re.fullmatch(r"\d{6,16}", content_id):
            return None
        news = source_item.get("news")
        news = news if isinstance(news, Mapping) else {}
        title = self._title(source_item)
        published_at = self._published_at(info.get("time") or news.get("time"))
        if not title or published_at is None:
            return None

        share_url = info.get("jump_url")
        if not isinstance(share_url, str):
            share = source_item.get("share")
            share_url = share.get("url") if isinstance(share, Mapping) else None
        if not isinstance(share_url, str):
            return None
        try:
            parsed = urlsplit(share_url)
            port = parsed.port
        except ValueError:
            return None
        match = _SHARE_PATH.fullmatch(parsed.path)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname is None
            or parsed.hostname.casefold() != "news.10jqka.com.cn"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or match is None
        ):
            return None
        try:
            expected_encoded = encode_news_seq(content_id)
        except ValueError:
            return None
        if match.group(1) != expected_encoded:
            return None

        date_path = published_at.strftime("%Y%m%d")
        article_url = f"https://news.10jqka.com.cn/{date_path}/c{content_id}.shtml"
        source_name = self._source_name(source_item, info, news)
        return self._article_row(
            topic_code,
            content_id,
            "news",
            title,
            article_url,
            published_at,
            source_name,
            rank,
        )

    def _long_article_row(
        self,
        topic_code: str,
        source_item: Mapping[str, Any],
        info: Mapping[str, Any],
        rank: int,
    ) -> dict[str, object] | None:
        """Map the verified type=2 feed sequence ID to the existing PID detail route."""

        content_id = str(info.get("id") or "")
        if not re.fullmatch(r"\d{6,16}", content_id):
            return None
        title = self._title(source_item)
        # Long-article rows have title.content and info.time; their `news` field is null.
        published_at = self._published_at(info.get("time"))
        if not title or published_at is None:
            return None
        url = f"https://t.10jqka.com.cn/pid_{content_id}.shtml"
        return self._article_row(
            topic_code,
            content_id,
            "zhibo",
            title,
            url,
            published_at,
            self._source_name(source_item, info, {}),
            rank,
        )

    @staticmethod
    def _title(source_item: Mapping[str, Any]) -> str:
        title_value = source_item.get("title")
        title = title_value.get("content") if isinstance(title_value, Mapping) else title_value
        return title.strip() if isinstance(title, str) else ""

    @staticmethod
    def _published_at(source_time: object) -> datetime | None:
        if isinstance(source_time, bool) or not isinstance(source_time, (str, int, float)):
            return None
        try:
            milliseconds = int(source_time)
            if str(source_time).strip() != str(milliseconds):
                return None
            return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).astimezone(_SHANGHAI)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _source_name(
        source_item: Mapping[str, Any],
        info: Mapping[str, Any],
        news: Mapping[str, Any],
    ) -> str | None:
        candidates: list[object] = [news.get("source"), source_item.get("sourceName"), info.get("sourceName")]
        for key in ("media", "source"):
            media = source_item.get(key)
            if isinstance(media, Mapping):
                candidates.append(media.get("name"))
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return re.sub(r"^\s*来源\s*", "", candidate).strip() or None
        return None

    @staticmethod
    def _article_row(
        topic_code: str,
        content_id: str,
        content_type: str,
        title: str,
        article_url: str,
        published_at: datetime,
        source_name: str | None,
        rank: int,
    ) -> dict[str, object]:
        return {
            "data": {
                "topicCode": topic_code,
                "rank": rank,
                "contentId": content_id,
                "contentType": content_type,
                "title": title,
                "url": article_url,
                "publishedAt": published_at,
                "sourceName": source_name,
            }
        }

    def _json_get(self, url: str) -> Mapping[str, Any]:
        request = Request(
            url,
            headers=build_headers(
                accept="application/json, text/javascript, */*;q=0.8",
                referer="https://t.10jqka.com.cn/",
            ),
        )
        try:
            response = self._open(request, timeout=DEFAULT_TIMEOUT_SECONDS)
            with response if hasattr(response, "__enter__") else _ResponseContext(response) as stream:
                status = getattr(stream, "status", None) or stream.getcode()
                body = stream.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            self._fail(f"topic API returned {http_status_failure_reason(exc.code) or f'HTTP {exc.code}'}")
        except (URLError, TimeoutError, OSError) as exc:
            self._fail(f"topic API transport failure: {type(exc).__name__}: {exc}")
        if http_status_failure_reason(int(status)):
            self._fail(f"topic API returned {http_status_failure_reason(int(status))}")
        if len(body) > _MAX_RESPONSE_BYTES:
            self._fail("topic API response exceeded the 4 MB safety limit")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._fail(f"topic API returned invalid JSON ({type(exc).__name__})")
        if not isinstance(payload, Mapping):
            self._fail("topic API response must be an object")
        status_code = payload.get("status_code")
        if status_code not in (None, 0, "0", 200, "200"):
            self._fail(f"topic API status_code={status_code!r}: {payload.get('status_msg')!r}")
        return payload

    def _fail(self, message: str) -> None:
        raise ProviderError(self.source, message)


class _ResponseContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, *_args: object) -> None:
        close = getattr(self.response, "close", None)
        if callable(close):
            close()


__all__ = ["THSTopicArticlesProvider", "TOPIC_PROVIDER_ID", "TOPIC_RECOMMEND_URL"]
