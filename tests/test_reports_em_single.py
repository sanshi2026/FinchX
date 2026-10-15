"""东方财富独立入口的协议、详情和结果完整性回归。"""
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx._common.errors import SourceError
from finchx.sources.eastmoney import reports_single as em

ID = 'AP202610141830470846'


def catalog(identity=ID, **kwargs):
    return {'infoCode': identity, 'title': '目录标题', 'orgSName': '机构',
            'columnType': '个股研报', 'publishDate': '2026-10-14 00:00:00.000',
            'reportType': 2, 'stockCode': '002015', 'stockName': '协鑫能科', **kwargs}


def page(rows=None, **kwargs):
    return 'research(' + json.dumps({'hits': 1, 'TotalPage': 1, 'pageNo': 1,
                                     'data': [catalog()] if rows is None else rows, **kwargs}, ensure_ascii=False) + ');'


def html(identity=ID, title='正式标题', day='2026-10-14', cls=False, text='真实摘要', pdf=True, **kwargs):
    meta = {'info_code': identity, 'notice_title': title, 'notice_date': day + ' 00:00:00',
            'source_sample_name': '机构', 'researcher': '研究员', 'attach_pages': '6',
            'security': [{'stock': '002015', 'short_name': '协鑫能科', 'market_uni': '0'}], **kwargs}
    content = '<div ' + ('class' if cls else 'id') + '="ctx-content"><p>' + text + '</p></div>' if text else ''
    return '<script>var zwinfo=' + json.dumps(meta, ensure_ascii=False) + ';</script>' + content + ('<a class="pdf-link" href="https://pdf.example/report.pdf">原文</a>' if pdf else '')


def item(identity=ID, title='目录标题', institute='机构', day='2026-10-14'):
    d = dict.fromkeys(em._FIELDS)
    d.update(info_code=identity, title=title, institute=institute, publication_date=day,
             url='https://data.eastmoney.com/report/zw_stock.jshtml?infocode=' + identity)
    return d


def test_catalog_contract_and_native_fields(monkeypatch):
    def read(url, **kwargs):
        q = parse_qs(urlsplit(url).query, keep_blank_values=True)
        assert q['qType'] == q['orgCode'] == q['author'] == ['*']
        assert q['beginTime'] == ['2026-10-14'] and q['endTime'] == ['']
        assert 'keyword' not in q
        return page()
    monkeypatch.setattr(em.http, 'get_text', read)
    rows, cursor = em._catalog_page(1, '2026-10-14', None, timeout=3)
    assert cursor is None and set(rows[0]) == set(em._FIELDS)
    assert rows[0]['stock_code'] == '002015'
    assert rows[0]['publication_date'] == '2026-10-14'
    assert rows[0]['rating'] is None


@pytest.mark.parametrize('body', ['{}', 'research({broken})', page(hits=True), page(pageNo=2),
                                  page(TotalPage=0), page(rows=[]), page(rows=[catalog(), catalog()]),
                                  page(rows=[catalog(columnType='未知')]), page(rows=[catalog(infoCode='bad')]),
                                  page(rows=[catalog(publishDate='2026-02-30 00:00:00.000')])])
def test_catalog_rejects_invalid_protocol(monkeypatch, body):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: body)
    with pytest.raises(SourceError):
        em._catalog_page(1, None, None, timeout=3)


@pytest.mark.parametrize('category,route', list(em._ROUTES.items()))
def test_real_detail_route(monkeypatch, category, route):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: page(rows=[catalog(columnType=category)]))
    rows, _ = em._catalog_page(1, None, None, timeout=3)
    assert '/' + route + '.jshtml?' in rows[0]['url']


@pytest.mark.parametrize('cls', [False, True])
def test_detail_extracts_both_containers_and_related_securities(monkeypatch, cls):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: html(cls=cls, rating='AA', star='1'))
    result = em._detail(item(), timeout=3)
    assert result['content'] == '真实摘要' and result['content_type'] == 'summary'
    assert result['title'] == '正式标题' and result['pdf_pages'] == 6
    assert result['securities'] == [{'code': '002015', 'name': '协鑫能科', 'market_code': '0'}]
    assert result['rating'] is None and result['column_type'] is None
    assert result['stock_code'] is None  # 相关证券不推断为主股票。


@pytest.mark.parametrize('body', [html(identity='AP999'), html(text='', pdf=False), '<div>门禁</div>',
                                  html(security='bad'), html(attach_pages=True)])
def test_detail_failure_is_explicit(monkeypatch, body):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: body)
    with pytest.raises(SourceError):
        em._detail(item(), timeout=3)


def test_no_attachment_is_confirmed_empty(monkeypatch):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: html(pdf=False))
    assert em._detail(item(), timeout=3)['pdf_urls'] == []


@pytest.mark.parametrize('keyword', [None, '', '   ', '\u3000', '\t\n'])
def test_empty_keyword_routes_to_catalog(monkeypatch, keyword):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([], None))
    monkeypatch.setattr(em, '_search_page', lambda *a, **k: pytest.fail('unexpected search'))
    assert em.em_fetch(keyword=keyword, timeout=3) == []


def test_nonempty_keyword_native_search(monkeypatch):
    def search(word, page, **kwargs):
        assert word == '光模块'
        return [item()], None
    monkeypatch.setattr(em, '_search_page', search)
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: pytest.fail('unexpected catalogue'))
    monkeypatch.setattr(em, '_detail', lambda row, **k: {**row, 'content': '摘要', 'pdf_urls': []})
    rows = em.em_fetch(keyword=' 光模块 ', timeout=3)
    assert len(rows) == 1 and set(rows[0]) == set(em._FIELDS)


@pytest.mark.parametrize('kwargs', [{'limit': True}, {'limit': 0}, {'keyword': 1}, {'keyword': 'x\n'},
                                   {'keyword': '\ud800'}, {'start_date': '2026-13-01'},
                                   {'start_date': '2026-10-15', 'end_date': '2026-10-14'}])
def test_bad_arguments(kwargs):
    with pytest.raises(ValueError):
        em.em_fetch(timeout=3, **kwargs)


@pytest.mark.parametrize('day', ['2026-10-14', '20261014', '2026/10/14', '2026-10-14 00:00:00',
                                '20261014 12:34:56', '2026/10/14 23:59:59'])
def test_six_date_formats(monkeypatch, day):
    def fetch(page, start, end, **kwargs):
        assert start == end == '2026-10-14'
        return [], None
    monkeypatch.setattr(em, '_catalog_page', fetch)
    assert em.em_fetch(start_date=day, end_date=day, timeout=3) == []


def test_detail_date_correction_dedup_and_resume(monkeypatch):
    calls = []
    def fetch(page, *a, **k):
        calls.append(page)
        return ([item('AP1'), item('AP2')] if page == 1 else [item('AP3', title='另一篇')], 2 if page == 1 else None)
    def detail(row, **kwargs):
        return {**row, 'publication_date': '2026-10-13' if row['info_code'] == 'AP1' else '2026-10-14', 'content': row['info_code']}
    monkeypatch.setattr(em, '_catalog_page', fetch)
    monkeypatch.setattr(em, '_detail', detail)
    rows = em.em_fetch(limit=2, start_date='2026-10-14', timeout=3)
    assert calls == [1, 2] and [r['info_code'] for r in rows] == ['AP2', 'AP3']


def test_exact_title_institute_different_dates_keep_whole_records(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1', day='2026-10-13'), item('AP2')], None))
    monkeypatch.setattr(em, '_detail', lambda row, **k: {**row, 'content': row['info_code']})
    rows = em.em_fetch(timeout=3)
    assert [(r['info_code'], r['content'], r['publication_date']) for r in rows] == [
        ('AP2', 'AP2', '2026-10-14'), ('AP1', 'AP1', '2026-10-13')]


def test_unknown_meta_keeps_native_ids_separate(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1', institute=None), item('AP2', institute=None)], None))
    monkeypatch.setattr(em, '_detail', lambda row, **k: row)
    assert len(em.em_fetch(timeout=3)) == 2


def test_missing_list_date_can_be_confirmed_in_detail(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item(day=None)], None))
    monkeypatch.setattr(em, '_detail', lambda row, **k: {**row, 'publication_date': '2026-10-14'})
    assert len(em.em_fetch(start_date='2026-10-14', timeout=3)) == 1


def test_partial_details_never_return_success(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1'), item('AP2', title='另')], None))
    def detail(row, **kwargs):
        if row['info_code'] == 'AP2':
            raise SourceError('eastmoney', '详情失败')
        return row
    monkeypatch.setattr(em, '_detail', detail)
    with pytest.raises(SourceError):
        em.em_fetch(timeout=3)


def test_real_overlap_progress_is_not_business_stagnation(monkeypatch):
    def fetch(page, *a, **kwargs):
        return [item('AP' + str(page))], page + 1 if page < 5 else None
    monkeypatch.setattr(em, '_catalog_page', fetch)
    monkeypatch.setattr(em, '_detail', lambda row, **kwargs: row)
    assert len(em.em_fetch(limit=2, timeout=3)) == 1


def test_three_repeated_native_pages_fail(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda page, *a, **k: ([item()], page + 1))
    monkeypatch.setattr(em, '_detail', lambda row, **kwargs: row)
    with pytest.raises(SourceError, match='停滞'):
        em.em_fetch(limit=2, timeout=3)


def test_backward_cursor_fails(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([], 1))
    with pytest.raises(SourceError, match='游标'):
        em.em_fetch(timeout=3)


@pytest.mark.parametrize('keyword', [None, '光模块'])
def test_each_http_gets_full_timeout_even_when_cumulative_elapsed_exceeds_it(monkeypatch, keyword):
    elapsed = [0.0]
    passed_timeouts = []
    # 旧共享deadline在这只仿真时钟下会在第二次HTTP前耗尽/缩短timeout。
    monkeypatch.setattr(em, 'monotonic', lambda: elapsed[0], raising=False)
    def read(url, *, timeout, **kwargs):
        passed_timeouts.append(timeout)
        assert timeout == 3
        elapsed[0] += 2
        path = urlsplit(url).path
        if path == '/report/dg':
            return page(rows=[catalog('AP1', title='标题1'), catalog('AP2', title='标题2')], hits=2)
        if path == '/search/jsonp':
            return 'research(' + json.dumps({'code': 0, 'hitsTotal': 2, 'result': {'researchReport': [
                {'code': 'AP' + str(i), 'title': '标题' + str(i), 'source': '机构',
                 'date': '2026-10-14 00:00:00'} for i in [1, 2]]}}) + ')'
        identity = parse_qs(urlsplit(url).query)['infocode'][0]
        return html(identity=identity, title='正式' + identity)
    monkeypatch.setattr(em.http, 'get_text', read)
    result = em.em_fetch(limit=2, keyword=keyword, timeout=3)
    assert len(result) == 2 and elapsed[0] == 6 > 3
    assert passed_timeouts == [3, 3, 3]


def test_native_search_preserves_stock_name_without_class_inference(monkeypatch):
    def read(url, **kwargs):
        params = json.loads(parse_qs(urlsplit(url).query)['param'][0])
        assert params['keyword'] == '光模块' and params['type'] == ['researchReport']
        assert set(params['param']['researchReport']) == {'client', 'pageSize', 'pageIndex'}
        return 'research(' + json.dumps({'code': 0, 'hitsTotal': 1, 'result': {'researchReport': [
            {'code': ID, 'title': '<em>光模块</em>', 'date': '2026-10-14 00:00:00',
             'source': '机构', 'stockName': '<em>新易盛</em>'}]}}) + ')'
    monkeypatch.setattr(em.http, 'get_text', read)
    rows, cursor = em._search_page('光模块', 1, timeout=3)
    assert cursor is None and rows[0]['stock_name'] == '新易盛'
    assert rows[0]['column_type'] is None and rows[0]['stock_code'] is None


@pytest.mark.parametrize('body', ['research({"code":0,"hitsTotal":1,"result":{"researchReport":[]}})',
                                  'research({"code":1})', 'research([])', 'other({})'])
def test_search_protocol_failures(monkeypatch, body):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: body)
    with pytest.raises(SourceError):
        em._search_page('光模块', 1, timeout=3)


def test_limit_one_does_not_read_unselected_group(monkeypatch):
    calls = []
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1'), item('AP2', title='其他')], None))
    def detail(row, **kwargs):
        calls.append(row['info_code'])
        if row['info_code'] != 'AP1':
            raise AssertionError('未选中组不该读详情')
        return row
    monkeypatch.setattr(em, '_detail', detail)
    assert len(em.em_fetch(limit=1, timeout=3)) == 1 and calls == ['AP1']


def test_same_day_complete_copy_wins_without_cross_record_merge(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1'), item('AP2')], None))
    def detail(row, **kwargs):
        return {**row, 'content': '摘要' if row['info_code'] == 'AP2' else None,
                'pdf_urls': ['https://pdf.example/' + row['info_code']]}
    monkeypatch.setattr(em, '_detail', detail)
    result = em.em_fetch(limit=1, timeout=3)
    assert result[0]['info_code'] == 'AP2' and result[0]['content'] == '摘要'
    assert result[0]['pdf_urls'] == ['https://pdf.example/AP2']


def test_selected_duplicate_detail_can_change_key_and_require_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1'), item('AP2')], None))
    def detail(row, **kwargs):
        calls.append(row['info_code'])
        return {**row, 'title': '正式另稿' if row['info_code'] == 'AP1' else row['title']}
    monkeypatch.setattr(em, '_detail', detail)
    assert len(em.em_fetch(limit=1, timeout=3)) == 1
    assert set(calls) == {'AP1', 'AP2'}


def test_duplicate_failure_cannot_hide_behind_valid_copy(monkeypatch):
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: ([item('AP1'), item('AP2')], None))
    def detail(row, **kwargs):
        if row['info_code'] == 'AP2':
            raise SourceError('eastmoney', '副本详情失败')
        return row
    monkeypatch.setattr(em, '_detail', detail)
    with pytest.raises(SourceError, match='副本'):
        em.em_fetch(limit=1, timeout=3)


def test_formal_institute_code_is_source_business_metadata(monkeypatch):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: html(company_code='80000007'))
    result = em._detail(item(), timeout=3)
    assert result['institute_code'] == '80000007'


def test_catalog_premature_short_page_fails(monkeypatch):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: page(hits=21, TotalPage=2))
    with pytest.raises(SourceError, match='条数不一致'):
        em._catalog_page(1, None, None, timeout=3)


@pytest.mark.parametrize('total,pages,rows', [(21, 1, 20), (21, 2, 19), (1, 1, 0), (20, 2, 20), (0, 2, 0)])
def test_catalog_same_response_counts_cannot_hide_incomplete_page(monkeypatch, total, pages, rows):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: page(
        rows=[catalog('AP' + str(i)) for i in range(rows)], hits=total, TotalPage=pages))
    with pytest.raises(SourceError):
        em._catalog_page(1, None, None, timeout=3)


def test_catalog_total_can_change_between_responses(monkeypatch):
    bodies = iter([page(rows=[catalog('AP' + str(i)) for i in range(20)], hits=21, TotalPage=2),
                   page(rows=[catalog('AP30'), catalog('AP31')], hits=22, TotalPage=2, pageNo=2)])
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: next(bodies))
    first, cursor = em._catalog_page(1, None, None, timeout=3)
    second, cursor = em._catalog_page(cursor, None, None, timeout=3)
    assert len(first) == 20 and len(second) == 2 and cursor is None


@pytest.mark.parametrize('pages', [0, 1])
def test_catalog_successful_empty_count_conventions(monkeypatch, pages):
    monkeypatch.setattr(em.http, 'get_text', lambda *a, **k: page(rows=[], hits=0, TotalPage=pages))
    assert em._catalog_page(1, None, None, timeout=3) == ([], None)


def test_large_limit_has_no_hidden_count_or_page_cap(monkeypatch):
    reads = []
    def fetch(cursor, *args, **kwargs):
        assert kwargs['timeout'] == 15
        start = (cursor - 1) * 20 + 1
        return [item('AP' + str(i), title='研报' + str(i)) for i in range(start, start + 20)], cursor + 1
    def detail(row, **kwargs):
        assert kwargs['timeout'] == 15
        reads.append(row['info_code'])
        return row
    monkeypatch.setattr(em, '_catalog_page', fetch)
    monkeypatch.setattr(em, '_detail', detail)
    result = em.em_fetch(limit=1000, timeout=15)
    assert len(result) == len(reads) == len(set(reads)) == 1000


def test_overlapping_pages_reuse_each_native_detail_once(monkeypatch):
    reads = []
    def fetch(cursor, *args, **kwargs):
        rows = [item('AP1', title='一')]
        if cursor > 1:
            rows.append(item('AP' + str(cursor), title=str(cursor)))
        return rows, cursor + 1
    monkeypatch.setattr(em, '_catalog_page', fetch)
    monkeypatch.setattr(em, '_detail', lambda row, **kwargs: reads.append(row['info_code']) or row)
    result = em.em_fetch(limit=3, timeout=15)
    assert len(result) == 3 and reads == ['AP1', 'AP2', 'AP3']


@pytest.mark.parametrize('missing', ['title', 'institute', 'publication_date'])
def test_three_part_key_missing_field_keeps_native_ids(monkeypatch, missing):
    records = [dict(item(identity), **{missing: None}) for identity in ('AP1', 'AP2')]
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: (records, None))
    monkeypatch.setattr(em, '_detail', lambda row, **k: row)
    result = em.em_fetch(limit=3, timeout=3)
    assert [r['info_code'] for r in result] == ['AP1', 'AP2']
    assert all(r[missing] is None for r in result)


@pytest.mark.parametrize('split', [False, True])
def test_formal_date_regroups_and_refills_without_repeating_details(monkeypatch, split):
    calls, reads = [], []
    def page(cursor, *args, **kwargs):
        calls.append(cursor)
        if cursor == 1:
            return [item('AP1'), item('AP2', day='2026-10-14' if split else '2026-10-13')], 2
        return [item('AP2'), item('AP3', title='补位')], None
    def detail(row, **kwargs):
        reads.append(row['info_code'])
        return dict(row, publication_date='2026-10-13' if split and row['info_code'] == 'AP2' else '2026-10-14')
    monkeypatch.setattr(em, '_catalog_page', page)
    monkeypatch.setattr(em, '_detail', detail)
    result = em.em_fetch(limit=2, timeout=3)
    assert calls == ([1] if split else [1, 2])
    assert sorted(reads) == (['AP1', 'AP2'] if split else ['AP1', 'AP2', 'AP3'])
    assert [r['info_code'] for r in result] == (['AP1', 'AP2'] if split else ['AP1', 'AP3'])


def test_saved_five_morning_report_pairs_keep_both_confirmed_days(monkeypatch):
    from pathlib import Path
    from finchx import FinchX

    # 实际SDK元信息离线重放分组；正文采用占位值，不冒充原生HTTP响应。
    fixture = Path(__file__).parent / 'fixtures/reports_fetch/em-cross-day-morning-metadata.json'
    metadata = json.loads(fixture.read_text(encoding='utf-8'))['records']
    records = [dict(item(r['info_code'], title=r['title'], institute=r['institute'],
                         day=r['publication_date']), pdf_urls=r['pdf_urls']) for r in metadata]
    monkeypatch.setattr(em, '_catalog_page', lambda *a, **k: (records, None))
    monkeypatch.setattr(em, '_detail', lambda row, **k: dict(row, content='离线分组测试摘要'))
    result = FinchX().reports.em_fetch(limit=500, start_date='2026-07-15', end_date='2026-10-15')
    assert len(result) == 10
    assert {r['info_code'] for r in result} == {r['info_code'] for r in metadata}
    for original in metadata:
        actual = next(r for r in result if r['info_code'] == original['info_code'])
        assert {key: actual[key] for key in original} == original
    assert [r['publication_date'] for r in result] == ['2026-10-15'] * 5 + ['2026-10-14'] * 5
