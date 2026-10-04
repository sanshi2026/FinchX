"""Client namespace implementation: _base."""

from __future__ import annotations

from typing import (
    Any,
)
from finchx.collectors import (
    FetchResult,
    InvalidRequest,
)
from finchx.datasets.definition import (
    DatasetDefinition,
)
from finchx.entities import (
    normalize_index_instrument,
    normalize_instrument,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finchx.client import FinchX


def _regulation_request(request_type: type[Any], **values: Any) -> Any:
    try:
        return request_type(**values)
    except (TypeError, ValueError) as exc:
        raise InvalidRequest(f"invalid {request_type.__name__}: {exc}") from exc


class _Namespace:
    __slots__ = ("_client",)

    def __init__(self, client: FinchX) -> None:
        self._client = client

    def _fetch(
        self,
        dataset: Any,
        request: Any,
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        return self._client.fetch(
            dataset,
            provider=provider,
            use_cache=use_cache,
            request=request,
        )


class _RequestNamespace(_Namespace):
    """Shared thin delegation for endpoints whose request model is the API."""

    def _fetch_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        request: Any,
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        if request is None:
            raise TypeError(f"{dataset.name} requires its request model")
        return self._fetch(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def _fetch_instrument_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        instrument: str,
        request_type: type[Any],
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        """Fetch a request model or build one from a single instrument input."""
        request = request_type(instrumentId=normalize_instrument(instrument))
        return self._fetch_request(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )

    def _fetch_index_request(
        self,
        dataset: DatasetDefinition[Any, Any],
        instrument: str,
        request_type: type[Any],
        *,
        provider: str | None,
        use_cache: bool | None,
    ) -> FetchResult[Any]:
        """Fetch an index request or resolve a bare code as an index."""
        request = request_type(instrumentId=normalize_index_instrument(instrument))
        return self._fetch_request(
            dataset,
            request,
            provider=provider,
            use_cache=use_cache,
        )
