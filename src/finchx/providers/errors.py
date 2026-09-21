"""Small provider-boundary errors with source context."""

from finchx.contracts import Source


class ProviderError(RuntimeError):
    """A provider could not retrieve or parse the requested source data."""

    def __init__(self, source: Source, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("provider error reason must be a non-empty string")
        self.source = source
        self.reason = reason
        super().__init__(f"provider {source.provider_id!r} failed: {reason}")
