"""Packaged FinchX v1 JSON Schema resources."""

from __future__ import annotations

import json
from importlib.resources.abc import Traversable
from importlib.resources import files
from typing import Any, Iterator


_SCHEMA_ROOT = files(__name__).joinpath("v1")


def schema_root() -> Traversable:
    """Return the packaged v1 schema directory as a traversable resource."""

    return _SCHEMA_ROOT


def iter_schema_resources() -> Iterator[Traversable]:
    """Yield all top-level v1 schema resources in stable name order."""

    yield from sorted(
        (resource for resource in _SCHEMA_ROOT.iterdir() if resource.name.endswith(".schema.json")),
        key=lambda resource: resource.name,
    )


def read_schema(name: str) -> dict[str, Any]:
    """Read and decode one top-level v1 schema by filename."""

    if not name.endswith(".schema.json") or "/" in name or "\\" in name:
        raise ValueError(f"invalid v1 schema name: {name!r}")
    resource = _SCHEMA_ROOT.joinpath(name)
    if not resource.is_file():
        raise FileNotFoundError(name)
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"schema is not a JSON object: {name!r}")
    return document


def read_schema_resource(relative_name: str) -> str:
    """Read a packaged v1 resource, including example JSON files, as text."""

    if relative_name.startswith("/") or ".." in relative_name.split("/"):
        raise ValueError(f"invalid v1 resource name: {relative_name!r}")
    resource = _SCHEMA_ROOT.joinpath(*relative_name.split("/"))
    if not resource.is_file():
        raise FileNotFoundError(relative_name)
    return resource.read_text(encoding="utf-8")


__all__ = ["iter_schema_resources", "read_schema", "read_schema_resource", "schema_root"]
