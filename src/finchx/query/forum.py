"""Public query service for the Taoguba activity-feed reply dataset."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Any

from finchx.collectors import FetchResult
from finchx.datasets.forum import FORUM_REPLIES_DATASET, ForumReply, ForumRepliesRequest
from finchx.providers.taoguba_forum import TaogubaForumProvider


def _normalize_user_names(user_names: Sequence[str] | None) -> tuple[str, ...] | None:
    if user_names is None:
        return None
    if isinstance(user_names, (str, bytes)) or not isinstance(user_names, Sequence):
        raise TypeError("user_names must be a sequence of usernames")
    values = tuple(user_names)
    if not values:
        raise ValueError("user_names must contain at least one non-empty username")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("user_names must contain only non-empty strings")
    return tuple(dict.fromkeys(value.strip() for value in values))


class ForumService:
    """Fetch qualified replies from the current account's activity feed."""

    def __init__(self, provider: TaogubaForumProvider | None = None) -> None:
        self.provider = provider or TaogubaForumProvider()

    def replies(
        self,
        *,
        cookies: str | Mapping[str, str],
        user_names: Sequence[str] | None = None,
        max_results: int | None = None,
        since: date | datetime | str | None = None,
        until: date | datetime | str | None = None,
    ) -> FetchResult[tuple[ForumReply, ...]]:
        names = _normalize_user_names(user_names)
        request = ForumRepliesRequest(
            userNames=names,
            maxResults=max_results,
            since=since,
            until=until,
        )
        fetch_with_warnings = getattr(self.provider, "fetch_replies_with_warnings", None)
        if callable(fetch_with_warnings):
            records, warnings = fetch_with_warnings(
                user_names=request.user_names,
                max_results=request.max_results,
                since=request.since,
                until=request.until,
                cookies=cookies,
            )
        else:
            records = self.provider.fetch_replies(
                user_names=request.user_names,
                max_results=request.max_results,
                since=request.since,
                until=request.until,
                cookies=cookies,
            )
            warnings = ()
        captured_at = max(
            (record.captured_at for record in records),
            default=self.provider.current_time().astimezone(timezone.utc),
        )
        return FetchResult(
            data=records,
            dataset=FORUM_REPLIES_DATASET,
            provider=self.provider.provider_id,
            captured_at=captured_at,
            warnings=warnings,
            provenance=(self.provider.source,),
        )


__all__ = ["ForumService"]
