import json


from finchx.schemas import (
    iter_schema_resources,
    read_schema,
    read_schema_resource,
    schema_root,
)


def test_v1_schemas_are_package_resources_with_stable_inventory():
    resources = list(iter_schema_resources())
    assert len(resources) == 52
    assert all(resource.name.endswith(".schema.json") for resource in resources)
    assert schema_root().joinpath("market-daily-replay.schema.json").is_file()
    assert schema_root().joinpath("market-deviation.schema.json").is_file()
    assert schema_root().joinpath("examples", "standard-record.json").is_file()
    assert read_schema("market-daily-replay.schema.json")["$id"].endswith(
        "/market-daily-replay.schema.json"
    )


def test_schema_loader_does_not_depend_on_repository_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    document = json.loads(read_schema_resource("examples/standard-record.json"))
    assert document["schemaVersion"] == "1.0"
    assert read_schema("units.schema.json")["$id"].endswith("/units.schema.json")
