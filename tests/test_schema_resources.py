import json
import os
import subprocess
import sys
from pathlib import Path


from finchx.schemas import (
    iter_schema_resources,
    read_schema,
    read_schema_resource,
    schema_root,
)


def test_v1_schemas_are_package_resources_with_stable_inventory():
    resources = list(iter_schema_resources())
    assert len(resources) == 62
    assert all(resource.name.endswith(".schema.json") for resource in resources)
    assert schema_root().joinpath("market-daily-replay.schema.json").is_file()
    assert schema_root().joinpath("market-deviation.schema.json").is_file()
    assert schema_root().joinpath("market-concept-list.schema.json").is_file()
    assert schema_root().joinpath("market-concept-quote-snapshot.schema.json").is_file()
    assert schema_root().joinpath("hotlist-stocks.schema.json").is_file()
    assert schema_root().joinpath("hotlist-sectors.schema.json").is_file()
    assert schema_root().joinpath("hotlist-convertible-bonds.schema.json").is_file()
    assert schema_root().joinpath("hotlist-etfs.schema.json").is_file()
    assert schema_root().joinpath("hotlist-content.schema.json").is_file()
    assert schema_root().joinpath("article-detail.schema.json").is_file()
    assert schema_root().joinpath("topic-article.schema.json").is_file()
    assert schema_root().joinpath("examples", "standard-record.json").is_file()
    assert read_schema("market-daily-replay.schema.json")["$id"].endswith(
        "/market-daily-replay.schema.json"
    )


def test_schema_loader_does_not_depend_on_repository_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    document = json.loads(read_schema_resource("examples/standard-record.json"))
    assert document["schemaVersion"] == "1.0"
    assert read_schema("units.schema.json")["$id"].endswith("/units.schema.json")


def test_schema_resource_type_import_falls_back_to_python310_location():
    code = """
import builtins
import warnings

warnings.simplefilter("ignore", DeprecationWarning)
from importlib.abc import Traversable
real_import = builtins.__import__
def hide_resources_abc(name, *args, **kwargs):
    if name == "importlib.resources.abc":
        raise ModuleNotFoundError(name=name)
    return real_import(name, *args, **kwargs)

builtins.__import__ = hide_resources_abc
from finchx.schemas import read_schema, schema_root
assert isinstance(schema_root(), Traversable)
assert read_schema("market-quote.schema.json")["type"] == "object"
"""
    source_root = str(Path(__file__).parents[1] / "src")
    env = {**os.environ, "PYTHONPATH": source_root}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)
