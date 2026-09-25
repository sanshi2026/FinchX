"""Errors raised at the FinchX Collector boundary."""

from __future__ import annotations

from typing import Any


class CollectorError(RuntimeError):
    """Base class for errors caused while resolving or executing a Collector fetch."""


class RoutingPolicyError(CollectorError):
    """The configured runtime routing policy is invalid."""


class UnknownDataset(CollectorError):
    """The requested Dataset name or schema version is not registered."""


class UnknownProvider(CollectorError):
    """The requested Provider identity is not registered."""


class ProviderDoesNotSupportDataset(CollectorError):
    """A registered Provider was asked for a Dataset it does not advertise."""


class ProviderExecutionError(CollectorError):
    """A Provider could not execute the selected Dataset request."""

    def __init__(
        self,
        dataset: str,
        provider: str,
        reason: str,
    ) -> None:
        self.dataset = dataset
        self.provider = provider
        self.reason = reason
        super().__init__(
            f"provider {provider!r} could not execute dataset {dataset!r}: {reason}"
        )


class MissingOptionalDependency(CollectorError):
    """The selected Provider needs an optional runtime dependency that is absent."""

    def __init__(self, dataset: str, provider: str, dependency: str) -> None:
        self.dataset = dataset
        self.provider = provider
        self.dependency = dependency
        install_hint = (
            "; install `finchx[jygs]`"
            if provider == "jiuyangongshe.daily_replay" and dependency == "playwright"
            else ""
        )
        super().__init__(
            f"provider {provider!r} for dataset {dataset!r} requires optional "
            f"dependency {dependency!r}{install_hint}"
        )


class AuthenticationError(CollectorError):
    """The selected Provider needs credentials or an authenticated session."""


class RateLimitError(CollectorError):
    """The upstream source rejected the request because of rate limiting."""


class Timeout(CollectorError):
    """The selected Provider did not complete within its bounded time."""


class SourceUnavailable(CollectorError):
    """The upstream source was temporarily unavailable."""


class NoData(CollectorError):
    """The Provider completed but had no usable data for this request."""


class SchemaDrift(CollectorError):
    """The source response no longer matches the Provider's expected schema."""


class InvalidRequest(CollectorError):
    """The request could not be constructed or is invalid for the Dataset."""


class AllProvidersFailed(CollectorError):
    """Every Provider allowed by the runtime policy failed."""

    def __init__(
        self,
        dataset: str,
        providers: tuple[str, ...],
        attempts: tuple[Any, ...],
        last_error: BaseException,
    ) -> None:
        self.dataset = dataset
        self.providers = providers
        self.attempts = attempts
        self.last_error = last_error
        provider_text = ", ".join(providers) if providers else "<none>"
        super().__init__(
            f"all allowed providers failed for dataset {dataset!r}: "
            f"[{provider_text}]; final error {type(last_error).__name__}: {last_error}"
        )


# A descriptive alias for callers that prefer a Collector-specific name.
CollectorFetchError = AllProvidersFailed


# The short names are the public runtime vocabulary.  The aliases make the
# boundary convenient for callers that prefer the conventional ``Error`` suffix.
UnknownDatasetError = UnknownDataset
UnknownProviderError = UnknownProvider
ProviderDoesNotSupportDatasetError = ProviderDoesNotSupportDataset
MissingOptionalDependencyError = MissingOptionalDependency


__all__ = [
    "AllProvidersFailed",
    "AuthenticationError",
    "CollectorError",
    "CollectorFetchError",
    "InvalidRequest",
    "MissingOptionalDependency",
    "MissingOptionalDependencyError",
    "NoData",
    "ProviderDoesNotSupportDataset",
    "ProviderDoesNotSupportDatasetError",
    "ProviderExecutionError",
    "RateLimitError",
    "RoutingPolicyError",
    "SchemaDrift",
    "SourceUnavailable",
    "Timeout",
    "UnknownDataset",
    "UnknownDatasetError",
    "UnknownProvider",
    "UnknownProviderError",
]
