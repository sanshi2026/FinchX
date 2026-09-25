"""Stable contracts for public Taoguba forum reply queries."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
import re
from typing import Any
from urllib.parse import urlparse

from pydantic import AnyUrl, Field, field_validator, model_validator

from finchx.contracts import Source
from finchx.contracts.models import ContractModel
from finchx.datasets.definition import DatasetDefinition


_DIGITS = re.compile(r"^[0-9]+$")


def _require_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("forum timestamps must be timezone-aware")
    if value.utcoffset().total_seconds() % 60:
        raise ValueError("forum timezone offsets must use whole-minute precision")
    return value


class ForumReply(ContractModel):
    """One reply with its complete, directly quoted parent comment."""

    reply_id: str = Field(alias="replyId", min_length=1, pattern=r"^[0-9]+$")
    user_id: str | None = Field(default=None, alias="userId", pattern=r"^[0-9]+$")
    username: str = Field(min_length=1)
    reply_time: datetime | None = Field(default=None, alias="replyTime")
    reply_content: str = Field(alias="replyContent", min_length=1)
    parent_username: str = Field(alias="parentUsername", min_length=1)
    parent_content: str = Field(alias="parentContent", min_length=1)
    post_id: str = Field(alias="postId", min_length=1)
    post_title: str | None = Field(default=None, alias="postTitle")
    post_url: AnyUrl = Field(alias="postUrl")
    reply_url: AnyUrl = Field(alias="replyUrl")
    source: Source
    captured_at: datetime = Field(alias="capturedAt")

    @field_validator("reply_id", mode="before")
    @classmethod
    def reply_id_must_be_source_digits(cls, value: Any) -> str:
        if not isinstance(value, str) or _DIGITS.fullmatch(value) is None:
            raise ValueError("replyId must be the source numeric reply ID")
        return value

    @field_validator("user_id", mode="before")
    @classmethod
    def optional_user_id_must_be_source_digits(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or _DIGITS.fullmatch(value) is None:
            raise ValueError("userId must be a source numeric user ID")
        return value

    @field_validator("reply_time", "captured_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @field_validator("reply_url")
    @classmethod
    def reply_url_must_be_source_locator(cls, value: AnyUrl) -> AnyUrl:
        text = str(value)
        match = re.fullmatch(r"https://www\.tgb\.cn/a/[^/?#]+/([0-9]+)#([0-9]+)", text)
        if match is None or match.group(1) != match.group(2):
            raise ValueError("replyUrl must use /a/{postId}/{replyId}#{replyId}")
        return value

    @model_validator(mode="after")
    def source_urls_and_ids_must_agree(self) -> "ForumReply":
        reply_url = urlparse(str(self.reply_url))
        post_url = urlparse(str(self.post_url))
        reply_match = re.fullmatch(r"/a/([^/?#]+)/([0-9]+)", reply_url.path)
        post_match = re.fullmatch(r"/a/([^/?#]+)/?", post_url.path)
        if reply_url.netloc != "www.tgb.cn" or post_url.netloc != "www.tgb.cn":
            raise ValueError("forum URLs must use www.tgb.cn")
        if reply_match is None or reply_url.fragment != self.reply_id:
            raise ValueError("replyUrl does not agree with replyId")
        if post_match is None or post_match.group(1) != self.post_id:
            raise ValueError("postUrl does not agree with postId")
        if reply_match.group(1) != self.post_id:
            raise ValueError("replyUrl does not agree with postId")
        return self

    @field_validator("username", "reply_content", "parent_username", "parent_content", "post_id")
    @classmethod
    def text_fields_must_be_non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("forum text fields must be non-empty")
        return value.strip()


class ForumRepliesRequest(ContractModel):
    """Non-credential controls for the current-account activity feed."""

    user_names: tuple[str, ...] | None = Field(default=None, alias="userNames")
    max_results: int | None = Field(default=None, alias="maxResults", ge=1, strict=True)
    since: date | datetime | None = None
    until: date | datetime | None = None

    @field_validator("user_names", mode="before")
    @classmethod
    def user_names_must_be_a_non_empty_sequence(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise TypeError("user_names must be a sequence of usernames")
        values = tuple(value)
        if not values:
            raise ValueError("user_names must contain at least one non-empty username")
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError("user_names must contain only non-empty strings")
        return tuple(dict.fromkeys(item.strip() for item in values))

    @field_validator("since", "until")
    @classmethod
    def datetime_bounds_must_be_aware(cls, value: date | datetime | None) -> date | datetime | None:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("forum since/until datetimes must include a timezone offset")
        return value

    @model_validator(mode="after")
    def date_bounds_must_be_ordered(self) -> "ForumRepliesRequest":
        if self.since is None or self.until is None:
            return self
        lower = self.since if isinstance(self.since, datetime) else datetime.combine(self.since, datetime.min.time())
        upper = self.until if isinstance(self.until, datetime) else datetime.combine(self.until, datetime.max.time())
        source_timezone = timezone(timedelta(hours=8))
        if lower.tzinfo is None:
            lower = lower.replace(tzinfo=source_timezone)
        if upper.tzinfo is None:
            upper = upper.replace(tzinfo=source_timezone)
        if lower > upper:
            raise ValueError("since must not be after until")
        return self


FORUM_REPLIES_DATASET: DatasetDefinition[ForumRepliesRequest, ForumReply] = DatasetDefinition(
    name="forum.replies",
    schema_version="1.0",
    request_type=ForumRepliesRequest,
    data_type=ForumReply,
)


__all__ = ["FORUM_REPLIES_DATASET", "ForumReply", "ForumRepliesRequest"]
