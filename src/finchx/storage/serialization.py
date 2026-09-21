"""Safe JSON serialization for FinchX storage payloads.

The format is deliberately typed and allow-listed.  It never evaluates code or
loads an arbitrary class name from a database payload.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import importlib
import json
import math
from typing import Any

from pydantic import BaseModel, ValidationError

from finchx.storage.errors import StorageSerializationError


_FORMAT = "finchx.storage.json.v1"


@lru_cache(maxsize=1)
def _model_registry() -> dict[str, type[BaseModel]]:
    """Return the explicit FinchX Pydantic model allow-list."""

    modules = (
        importlib.import_module("finchx.contracts.models"),
        importlib.import_module("finchx.entities.instrument"),
        importlib.import_module("finchx.datasets"),
    )
    registry: dict[str, type[BaseModel]] = {}
    for module in modules:
        for candidate in vars(module).values():
            if (
                isinstance(candidate, type)
                and issubclass(candidate, BaseModel)
                and candidate is not BaseModel
            ):
                model_id = f"{candidate.__module__}:{candidate.__qualname__}"
                registry[model_id] = candidate
    return registry


def _model_id(model: type[BaseModel]) -> str:
    return f"{model.__module__}:{model.__qualname__}"


def _url_text(value: Any) -> str | None:
    module = type(value).__module__
    method = getattr(value, "unicode_string", None)
    if module.startswith("pydantic.networks") and callable(method):
        return str(method())
    return None


def _encode(value: Any) -> Any:
    url = _url_text(value)
    if url is not None:
        return {"$type": "url", "value": url}
    if isinstance(value, BaseModel):
        return {
            "$type": "pydantic",
            "model": _model_id(type(value)),
            "value": _encode(value.model_dump(mode="python", by_alias=True)),
        }
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise StorageSerializationError("datetime payloads must be timezone-aware")
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise StorageSerializationError("Decimal payloads must be finite")
        return {"$type": "decimal", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StorageSerializationError("float payloads must be finite")
        return {"$type": "float", "value": value.hex()}
    if isinstance(value, Mapping):
        return {
            "$type": "dict",
            "items": [[_encode(key), _encode(item)] for key, item in value.items()],
        }
    if isinstance(value, tuple):
        return {"$type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, list):
        return {"$type": "list", "items": [_encode(item) for item in value]}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {"$type": "list", "items": [_encode(item) for item in value]}
    raise StorageSerializationError(
        f"unsupported payload type: {type(value).__module__}:{type(value).__qualname__}"
    )


def _decode(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        raise StorageSerializationError("encoded payload contains an unsupported JSON value")
    marker = value.get("$type")
    if not isinstance(marker, str):
        raise StorageSerializationError("encoded object is missing its type marker")

    if marker == "url":
        if not isinstance(value.get("value"), str):
            raise StorageSerializationError("encoded URL value is invalid")
        return value["value"]
    if marker == "datetime":
        raw = value.get("value")
        if not isinstance(raw, str):
            raise StorageSerializationError("encoded datetime value is invalid")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StorageSerializationError("encoded datetime value is invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise StorageSerializationError("encoded datetime must be timezone-aware")
        return parsed
    if marker == "date":
        raw = value.get("value")
        if not isinstance(raw, str):
            raise StorageSerializationError("encoded date value is invalid")
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise StorageSerializationError("encoded date value is invalid") from exc
    if marker == "decimal":
        raw = value.get("value")
        if not isinstance(raw, str):
            raise StorageSerializationError("encoded Decimal value is invalid")
        try:
            parsed = Decimal(raw)
        except InvalidOperation as exc:
            raise StorageSerializationError("encoded Decimal value is invalid") from exc
        if not parsed.is_finite():
            raise StorageSerializationError("encoded Decimal must be finite")
        return parsed
    if marker == "float":
        raw = value.get("value")
        if not isinstance(raw, str):
            raise StorageSerializationError("encoded float value is invalid")
        try:
            parsed = float.fromhex(raw)
        except ValueError as exc:
            raise StorageSerializationError("encoded float value is invalid") from exc
        if not math.isfinite(parsed):
            raise StorageSerializationError("encoded float must be finite")
        return parsed
    if marker in {"list", "tuple"}:
        items = value.get("items")
        if not isinstance(items, list):
            raise StorageSerializationError("encoded sequence items are invalid")
        decoded = [_decode(item) for item in items]
        return tuple(decoded) if marker == "tuple" else decoded
    if marker == "dict":
        items = value.get("items")
        if not isinstance(items, list):
            raise StorageSerializationError("encoded mapping items are invalid")
        result: dict[Any, Any] = {}
        try:
            for pair in items:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise StorageSerializationError("encoded mapping pair is invalid")
                result[_decode(pair[0])] = _decode(pair[1])
        except TypeError as exc:
            raise StorageSerializationError("encoded mapping key is not hashable") from exc
        return result
    if marker == "pydantic":
        model_id = value.get("model")
        if not isinstance(model_id, str):
            raise StorageSerializationError("encoded Pydantic model id is invalid")
        model = _model_registry().get(model_id)
        if model is None:
            raise StorageSerializationError(f"unsupported FinchX Pydantic model: {model_id}")
        try:
            return model.model_validate(_decode(value.get("value")))
        except (TypeError, ValueError, ValidationError) as exc:
            raise StorageSerializationError(
                f"encoded Pydantic model could not be validated: {model_id}"
            ) from exc
    raise StorageSerializationError(f"unknown payload type marker: {marker}")


def dumps(value: Any) -> str:
    """Encode one value as the versioned FinchX JSON storage format."""

    try:
        return json.dumps(
            {"format": _FORMAT, "value": _encode(value)},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except StorageSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise StorageSerializationError("payload could not be JSON encoded") from exc


def loads(payload: str) -> Any:
    """Decode one value, rejecting unknown or malformed storage formats."""

    try:
        envelope = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise StorageSerializationError("stored payload is not valid JSON") from exc
    if not isinstance(envelope, dict) or envelope.get("format") != _FORMAT:
        raise StorageSerializationError("stored payload has an unsupported format")
    if "value" not in envelope:
        raise StorageSerializationError("stored payload has no value")
    return _decode(envelope["value"])


__all__ = ["dumps", "loads"]
