"""Regression checks for the generated bilingual API reference."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import inspect
import importlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from finchx.collectors.core import FetchResult  # noqa: E402

from tools.generate_api_reference import (  # noqa: E402
    CATEGORY_SPECS,
    DESCRIPTION_ZH,
    EXAMPLE_SPECS,
    SUMMARY_ZH,
    endpoint_key,
    all_endpoint_keys,
    computed_endpoint_keys,
    provider_endpoint_keys,
    render,
)


def _examples(document: str) -> dict[str, str]:
    pattern = re.compile(
        r"<!-- api-example: (?P<key>[^ ]+) -->\n```python\n(?P<code>.*?)\n```",
        re.DOTALL,
    )
    return {match.group("key"): match.group("code") for match in pattern.finditer(document)}


def _assert_imports_exist(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                importlib.import_module(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = importlib.import_module(node.module or "")
            for alias in node.names:
                if alias.name != "*":
                    assert hasattr(module, alias.name), f"{alias.name} is not exported by {node.module}"


def _assert_no_unused_names(tree: ast.Module) -> None:
    loads = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                assert bound in loads, f"unused import: {bound}"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in loads and target.id != "result":
                    raise AssertionError(f"unused local: {target.id}")


class _RecordingCollector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, bool | None, dict[str, object]]] = []

    def fetch(self, dataset, provider=None, *, use_cache=None, **kwargs):
        self.calls.append((dataset.name, provider, use_cache, kwargs))
        return FetchResult(
            data=None,
            dataset=dataset,
            provider=provider or "example.fake",
            captured_at=datetime.now(timezone.utc),
        )


def test_generated_documents_are_current_and_have_all_capabilities():
    english = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")

    assert english == render("en")
    assert chinese == render("zh")
    assert set(_examples(english)) == set(EXAMPLE_SPECS) == set(all_endpoint_keys())
    assert len(_examples(english)) == len(all_endpoint_keys())
    count_phrase_en = (
        f"{len(provider_endpoint_keys())} data interfaces + "
        f"{len(computed_endpoint_keys())} computed capability = "
        f"{len(all_endpoint_keys())} public capabilities"
    )
    count_phrase_zh = (
        f"{len(provider_endpoint_keys())} 个数据接口 + "
        f"{len(computed_endpoint_keys())} 个计算能力 = "
        f"{len(all_endpoint_keys())} 个公开能力"
    )
    assert count_phrase_en in english
    assert count_phrase_zh in chinese


def test_capability_inventory_and_categories_are_derived_from_runtime_metadata():
    provider_keys = set(provider_endpoint_keys())
    computed_keys = set(computed_endpoint_keys())
    category_keys = [key for category in CATEGORY_SPECS for key in category.endpoint_keys]

    assert provider_keys
    assert computed_keys
    assert set(category_keys) == provider_keys | computed_keys
    assert len(category_keys) == len(set(category_keys))
    assert len(all_endpoint_keys()) == len(provider_keys) + len(computed_keys)


def test_generated_documents_have_no_pydantic_sentinel_or_mechanical_chinese_fallbacks():
    english = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")

    assert "PydanticUndefined" not in english
    assert "PydanticUndefined" not in chinese
    assert "Business field." not in english
    assert "业务字段。" not in chinese
    assert "Nested business model：" not in english
    assert " in a FetchResult" not in english
    assert " and return it in a FetchResult" not in english
    for document in (english, chinese):
        assert "Routing semantics" not in document
        assert "Declared by the Pydantic model." not in document
        assert "The public return annotation" not in document
        assert "Schema version" not in document
        assert "StandardRecord" not in document
        assert "record_id" not in document
        assert "entity_id" not in document
        assert "captured_at" not in document
    assert "Declared by the source signature." not in chinese
    assert "Public Client endpoint." not in chinese
    assert "Required / Optional" not in chinese
    assert "Provider-backed / Dataset-backed" not in chinese
    for description in DESCRIPTION_ZH:
        assert description not in chinese
    assert not re.search(r"\| (?:Yes|No) \|", chinese)
    for summary in SUMMARY_ZH.values():
        assert summary in chinese


def test_english_and_chinese_examples_are_identical_and_clean():
    english = _examples((ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8"))
    chinese = _examples((ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8"))
    assert english == chinese

    for key, code in english.items():
        tree = ast.parse(code, filename=f"<example:{key}>")
        compile(tree, f"<example:{key}>", "exec")
        _assert_imports_exist(tree)
        _assert_no_unused_names(tree)


def test_provider_backed_examples_dry_run_through_client_validation(monkeypatch):
    import finchx
    from finchx import FinchX as RealFinchX

    collector = _RecordingCollector()

    class RecordingFinchX(RealFinchX):
        def __init__(self):
            super().__init__(collector=collector)

    monkeypatch.setattr(finchx, "FinchX", RecordingFinchX)
    examples = _examples(render("en"))
    provider_keys = [key for key in all_endpoint_keys() if key != "market.deviation"]

    dataset_names = {endpoint_key(endpoint): endpoint.dataset.name for endpoint in finchx.CLIENT_ENDPOINTS}

    for key in provider_keys:
        before = len(collector.calls)
        tree = ast.parse(examples[key], filename=f"<example:{key}>")
        exec(compile(tree, f"<example:{key}>", "exec"), {})
        assert len(collector.calls) == before + 1, f"example did not fetch exactly once: {key}"
        assert collector.calls[-1][0] == dataset_names[key]


def test_deviation_example_is_explicitly_kept_out_of_provider_dry_run():
    code = _examples(render("en"))["market.deviation"]
    assert 'fx.market.deviation("600519", windows=(10, 30))' in code

    tree = ast.parse(code, filename="<example:market.deviation>")
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "deviation"
    )
    assert isinstance(call.args[0], ast.Constant)
    assert call.args[0].value == "600519"
    windows_node = next(keyword.value for keyword in call.keywords if keyword.arg == "windows")
    windows = ast.literal_eval(windows_node)
    assert windows == (10, 30)

    from finchx import FinchX
    signature = inspect.signature(FinchX(collector=_RecordingCollector()).market.deviation)
    bound = signature.bind("600519", windows=windows)
    assert bound.arguments["instrument_id"] == "600519"
    assert bound.arguments["windows"] == windows


def test_fundamental_industry_comparison_documents_alias_without_inventing_an_export():
    document = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    assert "FundamentalIndustryComparisonRequest" in document
    assert "finchx.datasets.IndustryComparisonRequest" in document
    assert "from finchx.datasets import FundamentalIndustryComparisonRequest" not in document


def test_latest_pool_request_tables_keep_trade_date_only_in_deprecated_note():
    document = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    for key in (
        "market.limit_up_pool",
        "market.limit_down_pool",
        "market.broken_limit_pool",
        "market.strong_pool",
        "market.yesterday_limit_up_pool",
    ):
        block = document.split(f"### `fx.{key}(...)`", 1)[1].split("\n### `fx.", 1)[0]
        parameters = block.split("**Parameters**", 1)[1].split("**Output fields**", 1)[0]
        assert "tradeDate" not in parameters
        assert "tradeDate" not in block.split("**Example**", 1)[1].split("**Parameters**", 1)[0]
        if "**Request fields**" in block:
            request_fields = block.split("**Request fields**", 1)[1].split("**Output fields**", 1)[0]
            assert "tradeDate" not in request_fields
        assert "| tradeDate |" in block
        assert "**Output fields**" in block

    assert document.count("**Deprecated compatibility:**") == 1


def test_common_provider_parameters_are_documented_once():
    english = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")

    assert english.count("### Common parameters") == 1
    assert chinese.count("### 公共参数") == 1
    assert "`provider`" in english and "`use_cache`" in english
    assert "`provider`" in chinese and "`use_cache`" in chinese
    for document, parameters_heading in (
        (english, "**Parameters**"),
        (chinese, "**参数**"),
    ):
        block = document.split("### `fx.market.quote_snapshot(...)`", 1)[1].split("\n### `fx.", 1)[0]
        parameters = block.split(parameters_heading, 1)[1].split("**Output fields**" if parameters_heading == "**Parameters**" else "**输出字段**", 1)[0]
        assert "| provider |" not in parameters
        assert "| use_cache |" not in parameters


def test_generator_has_one_active_renderer():
    source = (ROOT / "tools" / "generate_api_reference.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^def render\(", source, re.MULTILINE)) == 1


def test_generator_check_mode_passes():
    result = subprocess.run(
        [sys.executable, "tools/generate_api_reference.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
