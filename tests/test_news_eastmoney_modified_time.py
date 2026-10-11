"""财富号明确修改时间不能误判坏页面或冒充发布时间。"""

from pathlib import Path

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import news

_ID = "20260723190230347061020"
_URL = f"https://caifuhao.eastmoney.com/news/{_ID}"
_FIELDS = {"id", "title", "published_at", "source_name", "author", "content", "image_urls"}
_HTML = (Path(__file__).parent / "fixtures/news_eastmoney/cfh_modified_excerpt.html").read_text(encoding="utf-8")


def test_real_modified_header_retains_business_content_and_author_without_date_fill(monkeypatch):
    monkeypatch.setattr(news, "_get_html", lambda *a: _HTML)
    monkeypatch.setattr(news, "get_json", lambda *a, **k: pytest.fail("不能取目录回填发布时间"))
    result = news.em_get(_URL, timeout=3)
    assert set(result) == _FIELDS
    assert result["id"] == _ID and result["author"] == "聪明投资者"
    assert result["published_at"] is None
    assert result["source_name"] is None and result["image_urls"] == []
    assert result["title"].startswith("一只最有共识的AI龙头") and result["content"]


@pytest.mark.parametrize("replacement", ["修改于 2026年02月30日 10:16", "修改于 2026年07月24日 25:16",
    "修改于 2026年07月24日 10:16:60", "修改于 07月24日 10:16", "修改于", "更新于 2026年07月24日 10:16"])
def test_modified_wrong_date_or_unknown_label_still_fails(monkeypatch, replacement):
    html = _HTML.replace("修改于\n2026年07月24日 10:16", replacement)
    monkeypatch.setattr(news, "_get_html", lambda *a: html)
    with pytest.raises(SourceError, match="日期时间"):
        news.em_get(_URL, timeout=3)


@pytest.mark.parametrize("time,expected", [("2026年07月23日 19:02", "2026-07-23T19:02+08:00"),
    ("2026年07月23日 19:02:30", "2026-07-23T19:02:30+08:00")])
def test_bare_source_publication_time_keeps_precision(monkeypatch, time, expected):
    html = _HTML.replace("修改于\n2026年07月24日 10:16", time)
    monkeypatch.setattr(news, "_get_html", lambda *a: html)
    result = news.em_get(_URL, timeout=3)
    assert result["published_at"] == expected and set(result) == _FIELDS


@pytest.mark.parametrize("duplicate", ["2026年07月23日 19:02", "修改于 2026年07月24日 10:16"])
def test_duplicate_header_dates_remain_failure(monkeypatch, duplicate):
    html = _HTML.replace('<span class="txt">上海', f'<span class="txt">{duplicate}</span><span class="txt">上海')
    monkeypatch.setattr(news, "_get_html", lambda *a: html)
    with pytest.raises(SourceError, match="重复"):
        news.em_get(_URL, timeout=3)


def test_modified_header_does_not_relax_article_identity(monkeypatch):
    html = _HTML.replace(f'articleid:"{_ID}"', 'articleid:"1"')
    monkeypatch.setattr(news, "_get_html", lambda *a: html)
    with pytest.raises(SourceError, match="身份"):
        news.em_get(_URL, timeout=3)


def test_modified_marker_not_inferred_for_unverified_cms_header(monkeypatch):
    html = '''<script>var _NewsId="123"</script><div id="topbox"><div class="title">标题</div>
    <div class="infos"><span class="item">修改于 2026年07月24日 10:16</span></div></div><div id="ContentBody"><p>正文</p></div>'''
    monkeypatch.setattr(news, "_get_html", lambda *a: html)
    with pytest.raises(SourceError, match="日期时间"):
        news.em_get('https://finance.eastmoney.com/a/123.html', timeout=3)
