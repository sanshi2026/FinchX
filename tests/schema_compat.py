"""Compare JSON schemas across supported Pydantic emission versions.

Only redundant JSON Schema defaults and the known upstream Decimal spelling
are ignored. Application constraints and bundled schema bytes remain intact.
"""

DECIMAL_STRING_PATTERN = r"^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$"


def canonical_schema(value):
    if isinstance(value, list):
        return [canonical_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if (isinstance(value.get("enum"), list) and len(value["enum"]) == 1
            and ("const" not in value or value["const"] == value["enum"][0])):
        value = {**value, "const": value["enum"][0]}
        value.pop("enum")
    return {
        key: canonical_schema(item)
        for key, item in value.items()
        if not (
            (key == "pattern" and item == DECIMAL_STRING_PATTERN)
            or (key == "additionalProperties" and item is True)
        )
    }
