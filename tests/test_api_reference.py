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

from pydantic import AnyUrl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from finchx.collectors.core import FetchResult  # noqa: E402

from tools.generate_api_reference import (  # noqa: E402
    CATEGORY_SPECS,
    DESCRIPTION_ZH,
    EXAMPLE_SPECS,
    SUMMARY_ZH,
    annotation_text,
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
        if dataset.name == "hotlist.content":
            request = kwargs.get("request")
            topic_url = (
                "https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=T4dryo6"
                if getattr(request, "content_type", None) == "topic"
                else "https://stock.10jqka.com.cn/20260924/c680236250.shtml"
            )
            from finchx.contracts import (
                DataStatus,
                Provenance,
                ProvenanceClass,
                Quality,
                Source,
                StandardRecord,
            )

            record = StandardRecord(
                dataset=dataset.name,
                schemaVersion="1.0",
                recordId="example:hotlist-content:1",
                entityId="example:hotlist-content:1",
                capturedAt=datetime.now(timezone.utc),
                source=Source(providerId=provider or "example.fake"),
                status=DataStatus.LIVE,
                quality=Quality(),
                provenance=Provenance(recordClass=ProvenanceClass.STANDARDIZED),
                data={"url": topic_url},
            )
            return FetchResult(
                data=(record,),
                dataset=dataset,
                provider=provider or "example.fake",
                captured_at=datetime.now(timezone.utc),
            )
        if dataset.name == "articles.detail":
            from finchx.contracts import Source
            from finchx.datasets.article_detail import normalize_article_detail

            request = kwargs["request"]
            record = normalize_article_detail(
                request,
                {
                    "contentId": request.content_id,
                    "contentType": request.content_type or "news",
                    "title": "Fixture article",
                    "contentHtml": "<p>Fixture article body.</p>",
                    "contentText": "Fixture article body.",
                    "capturedAt": datetime.now(timezone.utc),
                },
                source=Source(providerId=provider or "example.fake"),
            )
            return FetchResult(
                data=record,
                dataset=dataset,
                provider=provider or "example.fake",
                captured_at=record.captured_at,
            )
        return FetchResult(
            data=(),
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
        f"This document covers {len(provider_endpoint_keys())} data interfaces and "
        f"{len(computed_endpoint_keys())} computed capability, for "
        f"{len(all_endpoint_keys())} core capabilities."
    )
    count_phrase_zh = (
        f"{len(provider_endpoint_keys())} 个数据接口 + "
        f"{len(computed_endpoint_keys())} 个计算能力 = "
        f"{len(all_endpoint_keys())} 个核心能力"
    )
    assert count_phrase_en in english
    assert count_phrase_zh in chinese


def test_equity_intraday_chinese_usage_names_are_exact():
    chinese = render("zh")
    expected = {
        "market.equity_intraday": "获取个股分时图。",
        "market.equity_intraday_5d": "获取个股5日分时图。",
    }

    for key, summary in expected.items():
        assert SUMMARY_ZH[key] == summary
        assert f"| `fx.{key}(...)` | {summary} |" in chinese
        assert f"**提供什么数据**\n{summary}" in chinese


def test_ranking_reference_documents_describe_public_strings_and_units():
    for language in ("en", "zh"):
        document = render(language)
        block = document.split("### `fx.market.ranking(...)`", 1)[1].split("### ", 1)[0]
        output_marker = "**Output fields**" if language == "en" else "**输出字段**"
        parameters = block.split(output_marker, 1)[0]

        assert "universe" not in parameters
        assert "from finchx.datasets" not in parameters
        for value in ("amount", "zdf", "volume", "asc", "desc"):
            assert value in parameters
        for internal in ("turnover", "change_percent", "ascending", "descending"):
            assert internal not in parameters
        assert "CNY" in parameters
        assert "shares" in parameters or "股" in parameters
        assert "ratio fraction" in parameters or "比例小数" in parameters
        assert "positive integer" in parameters or "正整数" in parameters
        assert "None" in parameters


def test_ohlcv_reference_documents_describe_public_adjustment_and_output_labels():
    for language in ("en", "zh"):
        document = render(language)
        block = document.split("### `fx.market.ohlcv(...)`", 1)[1].split("### ", 1)[0]
        output_marker = "**Output fields**" if language == "en" else "**输出字段**"
        parameters, output = block.split(output_marker, 1)

        mode = "Optional" if language == "en" else "可选"
        assert f"| adjustment | str \\| None | {mode} | None |" in parameters
        assert "qfq" in parameters
        assert "hfq" in parameters
        assert "None" in parameters
        assert "KlineAdjustment" not in parameters
        assert "none" in output
        assert "qfq" in output
        assert "hfq" in output
        assert "not_applicable" in output
        assert "KlineAdjustment" in output

        example = _examples(document)["market.ohlcv"]
        assert "from finchx.datasets import KlineAdjustment" not in example
        assert 'adjustment="qfq"' in example


def test_document_detail_operations_are_publicly_documented():
    for language in ("en", "zh"):
        document = render(language)
        signatures = (
            "fx.news.get_document(ref)",
            "fx.news.get_documents(refs)",
            "fx.disclosure.get_document(ref)",
            "fx.disclosure.get_documents(refs)",
            "fx.market_news.search(...)",
            "fx.market_news.get_document(ref)",
            "fx.market_news.get_documents(refs)",
            "fx.forum.replies(cookies=..., user_names=[...])",
        )
        for signature in signatures:
            marker = f"### `{signature}`"
            assert marker in document
            section = document.split(marker, 1)[1].split("### ", 1)[0]
            labels = (
                ("**What it provides**", "**Data source**", "**Example**", "**Parameters**", "**Output fields**")
                if language == "en"
                else ("**提供什么数据**", "**数据源**", "**示例**", "**参数**", "**输出字段**")
            )
            for label in labels:
                assert label in section
            assert "```python" in section
        for operation in (
            "fx.news.get_document",
            "fx.news.get_documents",
            "fx.disclosure.get_document",
            "fx.disclosure.get_documents",
            "fx.market_news.search",
            "fx.market_news.get_document",
            "fx.market_news.get_documents",
            "fx.forum.replies",
        ):
            assert operation in document
        assert "FetchResult[tuple[ForumReply, ...]]" in document
        assert "user_names" in document
        assert "FetchResult[document record]" in document
        assert "FetchResult[tuple[document record, ...]]" in document


def test_document_examples_chain_all_searches_through_fetch_result_data():
    operations = {
        "fx.news.get_document(ref)": "fx.news.search",
        "fx.news.get_documents(refs)": "fx.news.search",
        "fx.disclosure.get_document(ref)": "fx.disclosure.search",
        "fx.disclosure.get_documents(refs)": "fx.disclosure.search",
        "fx.market_news.get_document(ref)": "fx.market_news.search",
        "fx.market_news.get_documents(refs)": "fx.market_news.search",
    }

    for language in ("en", "zh"):
        document = render(language)
        for signature, search_call in operations.items():
            section = document.split(f"### `{signature}`", 1)[1].split("### ", 1)[0]
            example_label = "**Example**" if language == "en" else "**示例**"
            code = re.search(rf"{re.escape(example_label)}.*?```python\n(.*?)\n```", section, re.DOTALL)
            assert code is not None
            example = code.group(1)
            assert "from finchx import FinchX" in example
            assert "fx = FinchX()" in example
            assert f"search_result = {search_call}" in example
            assert "refs[0]" not in example
            assert "if search_result.data:" in example
            if "get_document(ref)" in signature:
                assert "ref = search_result.data[0]" in example
                assert "ref=search_result.data[0]" in example
            else:
                assert "refs=search_result.data" in example

        market_search = document.split("### `fx.market_news.search(...)`", 1)[1].split("### ", 1)[0]
        assert "FetchResult[tuple[NewsDocumentRef, ...]]" in market_search
        assert "result.to_dicts()" in market_search
        assert "does not return FetchResult" not in market_search


def test_capability_inventory_and_categories_are_derived_from_runtime_metadata():
    provider_keys = set(provider_endpoint_keys())
    computed_keys = set(computed_endpoint_keys())
    category_keys = [key for category in CATEGORY_SPECS for key in category.endpoint_keys]

    assert provider_keys
    assert computed_keys
    assert set(category_keys) == provider_keys | computed_keys
    assert len(category_keys) == len(set(category_keys))
    assert len(all_endpoint_keys()) == len(provider_keys) + len(computed_keys)


def test_reference_orders_related_interfaces_together_in_overview_and_details():
    for language, overview_heading in (
        ("en", "## 3. Interface overview"),
        ("zh", "## 3. 接口总览"),
    ):
        document = render(language)
        overview = document.split(overview_heading, 1)[1].split("## 4.", 1)[0]
        overview_keys = re.findall(r"\| `fx\.([^`(]+)\(\.\.\.\)", overview)
        detail_section = document.split("## 4.", 1)[1].split("## 5.", 1)[0]
        detail_keys = re.findall(r"^### `fx\.([^(`]+)\(", detail_section, re.MULTILINE)
        for keys in (overview_keys, detail_keys):
            for first, second in (
                ("market.breadth", "market.sentiment"),
                ("hotlist.sectors", "hotlist.stocks"),
                ("market.quote", "market.ranking"),
            ):
                index = keys.index(first)
                assert keys[index + 1] == second


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
        assert "record_id" not in document
        assert "entity_id" not in document
    assert "Declared by the source signature." not in chinese
    assert "Public Client endpoint." not in chinese
    assert "Required / Optional" not in chinese
    assert "Provider-backed / Dataset-backed" not in chinese
    for description in DESCRIPTION_ZH:
        assert description not in chinese
    assert not re.search(r"\| (?:Yes|No) \|", chinese)
    for summary in SUMMARY_ZH.values():
        assert summary in chinese


def test_pydantic_any_url_annotation_names_are_stable_across_versions():
    assert annotation_text(AnyUrl) == "AnyUrl"
    assert annotation_text(AnyUrl | None) == "AnyUrl | None"

    for document in (render("en"), render("zh")):
        assert "| Url |" not in document
        assert "| Url \\| None |" not in document


def test_english_and_chinese_examples_are_identical_and_clean():
    english = _examples((ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8"))
    chinese = _examples((ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8"))
    assert english.keys() == chinese.keys()

    for key, code in english.items():
        tree = ast.parse(code, filename=f"<example:{key}>")
        compile(tree, f"<example:{key}>", "exec")
        _assert_imports_exist(tree)
        _assert_no_unused_names(tree)
        zh_tree = ast.parse(chinese[key], filename=f"<example:{key}:zh>")
        assert ast.dump(tree, include_attributes=False) == ast.dump(zh_tree, include_attributes=False)


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
        calls = collector.calls[before:]
        if key == "articles.get":
            assert [call[0] for call in calls] == ["articles.detail"]
        elif key == "articles.from_topic":
            assert [call[0] for call in calls] == ["articles.topic"]
        else:
            assert len(calls) == 1, f"example did not fetch exactly once: {key}"
            assert calls[-1][0] == dataset_names[key]


def test_deviation_example_is_explicitly_kept_out_of_provider_dry_run():
    code = _examples(render("en"))["market.deviation"]

    tree = ast.parse(code, filename="<example:market.deviation>")
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "deviation"
    )
    instrument_node = next(keyword.value for keyword in call.keywords if keyword.arg == "instrument")
    assert ast.literal_eval(instrument_node) == "600519"
    windows_node = next(keyword.value for keyword in call.keywords if keyword.arg == "windows")
    windows = ast.literal_eval(windows_node)
    assert windows == (10, 30)

    from finchx import FinchX
    signature = inspect.signature(FinchX(collector=_RecordingCollector()).market.deviation)
    bound = signature.bind(instrument="600519", windows=windows)
    assert bound.arguments["instrument"] == "600519"
    assert bound.arguments["windows"] == windows


def test_public_reference_hides_internal_request_and_identity_models():
    document = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")
    for public_document in (document, chinese):
        assert "InstrumentId" not in public_document
        assert "InstrumentInput" not in public_document
        assert "Request fields" not in public_document
        assert "Request 字段" not in public_document
        assert "**Call**" not in public_document
        assert "**调用方式**" not in public_document
    assert "FundamentalIndustryComparisonRequest" not in document


def test_hotlist_options_and_ranking_criteria_are_clear_in_both_languages():
    documents = {
        "en": (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8"),
        "zh": (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8"),
    }
    allowed_values = {
        "hotlist.stocks": ("category", ("popular", "rising", "new", "technical", "value", "trend")),
        "hotlist.etfs": ("category", ("popular", "t0", "price_limit_20", "cross_border", "commodity")),
        "hotlist.content": ("content_type", ("topic", "comment", "article")),
        "hotlist.sectors": ("sector_type", ("concept", "industry", "index")),
    }
    for language, document in documents.items():
        heading, next_heading = ("**Parameters**", "**Output fields**") if language == "en" else ("**参数**", "**输出字段**")
        for endpoint, (parameter, values) in allowed_values.items():
            block = document.split(f"### `fx.{endpoint}(...)`", 1)[1].split("\n### `fx.", 1)[0]
            parameters = block.split(heading, 1)[1].split(next_heading, 1)[0]
            row = next(line for line in parameters.splitlines() if line.startswith(f"| {parameter} |"))
            assert all(f"`{value}`" in row for value in values)
            assert "Parameter." not in row and "参数。" not in row
            limit_row = next(line for line in parameters.splitlines() if line.startswith("| limit |"))
            if language == "en":
                assert "| int | Optional | 20 |" in limit_row
                assert "positive integer" in limit_row and "None" not in limit_row
            else:
                assert "| int | 可选 | 20 |" in limit_row
                assert "正整数" in limit_row and "None" not in limit_row

        ranking = document.split("### `fx.market.ranking(...)`", 1)[1].split("\n### `fx.", 1)[0]
        parameters = ranking.split(heading, 1)[1].split(next_heading, 1)[0]
        criterion = next(line for line in parameters.splitlines() if line.startswith("| criterion |"))
        assert all(f"`{value}`" in criterion for value in ("amount", "zdf", "volume"))
        if language == "en":
            assert "CNY" in criterion and "ratio fraction" in criterion and "shares" in criterion
            assert "maps to" not in criterion and "turnover" not in criterion and "change_percent" not in criterion
        else:
            assert "CNY" in criterion and "比例小数" in criterion and "单位为股" in criterion
            assert "映射" not in criterion and "metric criterion" not in criterion


def test_pool_trade_date_is_output_only_and_compatibility_copy_is_removed():
    document = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")
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
        example_section = block.split("**Example**", 1)[1].split("**Parameters**", 1)[0]
        example_code = re.search(r"```python\n(.*?)\n```", example_section, re.DOTALL)
        assert example_code is not None
        assert "tradeDate" not in example_code.group(1)
        if "**Request fields**" in block:
            request_fields = block.split("**Request fields**", 1)[1].split("**Output fields**", 1)[0]
            assert "tradeDate" not in request_fields
        assert "| tradeDate |" in block
        assert "**Output fields**" in block

    assert "Deprecated compatibility" not in document
    assert "latest snapshot stock pool" not in document.lower()
    assert "最新快照股票池" not in chinese
    assert "弃用兼容" not in chinese


def test_internal_routing_controls_are_hidden_from_public_references():
    english = (ROOT / "docs" / "DATA_API_REFERENCE.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs" / "DATA_API_REFERENCE.zh-CN.md").read_text(encoding="utf-8")

    assert "### Common parameters" not in english
    assert "### 公共参数" not in chinese
    for document, parameters_heading in (
        (english, "**Parameters**"),
        (chinese, "**参数**"),
    ):
        assert "provider=" not in document
        assert "use_cache=" not in document
        assert "Pass `provider=`" not in document
        assert "可用 `provider=`" not in document
        for block in _examples(document).values():
            assert "provider=" not in block
            assert "use_cache=" not in block
        for block in document.split("### `fx.")[1:]:
            if parameters_heading not in block:
                continue
            parameters = block.split(parameters_heading, 1)[1].split(
                "**Output fields**" if parameters_heading == "**Parameters**" else "**输出字段**", 1
            )[0]
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
