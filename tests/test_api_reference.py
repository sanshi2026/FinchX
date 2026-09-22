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
from finchx import __version__  # noqa: E402
from finchx.collectors.core import FetchResult  # noqa: E402

from tools.generate_api_reference import (  # noqa: E402
    DESCRIPTION_ZH,
    EXAMPLE_SPECS,
    MINIMUM_INPUT_ZH,
    SUMMARY_ZH,
    endpoint_key,
    all_endpoint_keys,
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
    assert f"from the {__version__} public Client" in english
    assert f"根据 {__version__} 公开 Client" in chinese


def test_generated_documents_have_no_pydantic_sentinel_or_mechanical_chinese_fallbacks():
    english = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")

    assert "PydanticUndefined" not in english
    assert "PydanticUndefined" not in chinese
    assert "Declared by the Pydantic model." not in chinese
    assert "Declared by the source signature." not in chinese
    assert "Public Client endpoint." not in chinese
    assert "Required / Optional" not in chinese
    assert "Provider-backed / Dataset-backed" not in chinese
    for description in DESCRIPTION_ZH:
        assert description not in chinese
    assert set(MINIMUM_INPUT_ZH) == {spec.minimum_input_en for spec in EXAMPLE_SPECS.values()}
    for spec in EXAMPLE_SPECS.values():
        assert spec.minimum_input_en in english
        assert spec.minimum_input_zh in chinese

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
    assert "fx.market.deviation(instrument_id, windows=(10, 30))" in code

    tree = ast.parse(code, filename="<example:market.deviation>")
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "deviation"
    )
    assert isinstance(call.args[0], ast.Name)
    assert call.args[0].id == "instrument_id"
    windows_node = next(keyword.value for keyword in call.keywords if keyword.arg == "windows")
    windows = ast.literal_eval(windows_node)
    assert windows == (10, 30)

    from finchx import FinchX
    from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

    instrument_id = InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )
    signature = inspect.signature(FinchX(collector=_RecordingCollector()).market.deviation)
    bound = signature.bind(instrument_id, windows=windows)
    assert bound.arguments["instrument_id"] == instrument_id
    assert bound.arguments["windows"] == windows


def test_fundamental_industry_comparison_documents_alias_without_inventing_an_export():
    document = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    assert "FundamentalIndustryComparisonRequest" in document
    assert "finchx.datasets.IndustryComparisonRequest" in document
    assert "from finchx.datasets import FundamentalIndustryComparisonRequest" not in document


def test_generator_check_mode_passes():
    result = subprocess.run(
        [sys.executable, "tools/generate_api_reference.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
