"""东方财富原生搜索与摘要适配器的小型独立协议样本。"""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import reports


_ID = 'AP202609291829994966'


def _row(**updates):
    return {'code': _ID, 'title': 'NPO产业<em>光</em><em>模块</em>&amp;发展', 'source': '群益证券', 'date': '2026-09-29 00:00:00', **updates}


def _response(rows=None, **updates):
    return 'research(' + json.dumps({'code': 0, 'bizCode': '', 'hitsTotal': 21, 'result': {'researchReport': [_row()] if rows is None else rows}, **updates}, ensure_ascii=False) + ');'


def _search(monkeypatch, body):
    monkeypatch.setattr(reports.http, 'get_text', lambda *a, **k: body)
    return reports.search_page('光模块', 1, timeout=3)


def _candidate():
    return {'source': 'eastmoney', 'title': '搜索标题', 'institute': None, 'publication_date': None, 'url': reports._DETAIL_URL + '?infocode=' + _ID, 'content': None, 'content_type': None, 'pdf_urls': None, '_id': _ID, '_date_text': None}


def _detail(monkeypatch, body):
    monkeypatch.setattr(reports.http, 'get_text', lambda *a, **k: body)
    return reports.get_detail(_candidate(), timeout=3)


def test_search_native_keyword_and_fields(monkeypatch):
    calls = []
    def read(url, **kwargs):
        calls.append((url, kwargs))
        return _response()
    monkeypatch.setattr(reports.http, 'get_text', read)
    rows, cursor = reports.search_page('光模块', 1, timeout=4)
    query = parse_qs(urlsplit(calls[0][0]).query)
    param = json.loads(query['param'][0])
    assert query['cb'] == ['research']
    assert param['keyword'] == '光模块'
    assert param['type'] == ['researchReport']
    assert param['param']['researchReport'] == {'client': 'web', 'pageSize': 20, 'pageIndex': 1}
    assert calls[0][1]['timeout'] == 4
    assert rows[0]['title'] == 'NPO产业光模块&发展'
    assert rows[0]['institute'] == '群益证券'
    assert rows[0]['_id'] == _ID
    assert rows[0]['publication_date'] == '2026-09-29'
    assert rows[0]['url'] == 'http://data.eastmoney.com/report/zw_stock.jshtml?infocode=' + _ID
    assert rows[0]['pdf_urls'] is None
    assert rows[0]['content'] is None and rows[0]['content_type'] is None
    assert cursor == 2


@pytest.mark.parametrize('body', ['{}', 'wrong({})', 'research({});alert(1)', 'research({bad});', _response(code=1), _response(code=True), _response(bizCode='ACCESS'), _response(hitsTotal=None), _response(result={}), _response(result={'researchReport': None})])
def test_invalid_search_jsonp_status_structure(monkeypatch, body):
    with pytest.raises(SourceError):
        _search(monkeypatch, body)


@pytest.mark.parametrize('row', [_row(code='300502'), _row(code=None), _row(code=123), _row(date='2026-02-30'), _row(date='2026-09-29 25:00:00'), _row(date=123), _row(source=[]), _row(title=3), None])
def test_invalid_search_identity_date(monkeypatch, row):
    with pytest.raises(SourceError):
        _search(monkeypatch, _response([row]))


def test_search_duplicates_and_short_page_do_not_end_early(monkeypatch):
    rows, next_cursor = _search(monkeypatch, _response([_row(), _row()], hitsTotal=500))
    assert len(rows) == 2 and next_cursor == 2
    rows, next_cursor = _search(monkeypatch, _response([_row(), _row()], hitsTotal=1))
    assert len(rows) == 2 and next_cursor is None


@pytest.mark.parametrize('total', [0, 500])
def test_legal_empty(monkeypatch, total):
    assert _search(monkeypatch, _response([], hitsTotal=total)) == ([], None)


def test_optional_metadata_missing(monkeypatch):
    rows, _ = _search(monkeypatch, _response([_row(title=None, source=None, date=None)]))
    assert rows[0]['title'] is rows[0]['institute'] is rows[0]['publication_date'] is None


def test_target_summary_pdf_and_identity(monkeypatch):
    body = '''<h1 id="zw-title">正式光模块&amp;报告</h1>
    <a class="pdf-link" href="//pdf.dfcfw.com/actual.pdf?x=1&amp;y=2">原文</a>
    <nav>推荐无关</nav><div id="ctx-content"><p>摘要甲&amp;乙</p><p>摘要第二段</p><img src="/a.png"></div>
    <aside>推荐其他</aside><script>var zwinfo={"info_code":"%s","notice_date":"2026-09-29 00:00:00","source_sample_name":"群益证券"};</script>''' % _ID
    original = _candidate()
    monkeypatch.setattr(reports.http, 'get_text', lambda *a, **k: body)
    result = reports.get_detail(original, timeout=3)
    assert result is not original and original['content'] is None
    assert result['title'] == '正式光模块&报告'
    assert result['institute'] == '群益证券'
    assert result['publication_date'] == '2026-09-29'
    assert result['content_type'] == 'summary'
    assert '摘要甲&乙' in result['content'] and '摘要第二段' in result['content']
    assert '推荐' not in result['content']
    assert 'http://data.eastmoney.com/a.png' in result['content']
    assert result['pdf_urls'] == ['http://pdf.dfcfw.com/actual.pdf?x=1&y=2']


def test_summary_without_optional_identity_or_pdf(monkeypatch):
    result = _detail(monkeypatch, '<div class="ctx-content" id="ctx-content"><p>有效摘要讨论登录与付费业务。</p></div>')
    assert result['pdf_urls'] == []
    assert result['content_type'] == 'summary'
    assert result['title'] == '搜索标题'


def test_pdf_only_and_relative_links(monkeypatch):
    result = _detail(monkeypatch, '<a class="pdf-link" href="/report/original.pdf">原文</a><a class="pdf-link" href="/report/original.pdf">重复</a><a href="/unrelated.pdf">推荐</a>')
    assert result['content'] is result['content_type'] is None
    assert result['pdf_urls'] == ['http://data.eastmoney.com/report/original.pdf']


@pytest.mark.parametrize('body', ['<html>请登录后查看</html>', '<div id="ctx-content"></div>', '<div id="ctx-content"><p>损坏摘要</p>', '<div id="ctx-content">第一段</div><div id="ctx-content">重复段</div>', '<a class="pdf-link" href="javascript:alert(1)">查看</a>', '<div id="ctx-content">摘要</div><script>var zwinfo={bad};</script>', '<div id="ctx-content">摘要</div><script>var zwinfo={"info_code":"AP1"};</script>', '<div id="ctx-content">摘要</div><script>var _us_zixun_Id="AP1";</script>'])
def test_detail_gates_invalid_and_conflicting_identity(monkeypatch, body):
    with pytest.raises(SourceError):
        _detail(monkeypatch, body)
