"""受控官网响应/浏览器测试；这里的成功复盘都是构造数据，不是真实样本。"""

from copy import deepcopy
from datetime import date
import json
from types import SimpleNamespace

import pytest

from finchx import SourceError
from finchx.sources.jiuyangongshe import replay

DATE = '2026-09-30'
SESSION = 'controlled-session-canary'


def count(day=DATE, total=1):
    return {'errCode': '0', 'data': {'date': day, 'all': total, 'recommend': 0}}


def stock(code='sh600519'):
    return {'code': code, 'name': '受控股票', 'article': {'action_info': {
        'price': 1234, 'shares_range': -102, 'time': '09:30:00',
        'num': '首板', 'expound': '第一行\n第二行\n完整解析原文',
    }}}


def field():
    return {'errCode': 0, 'data': [{'date': DATE, 'name': '受控题材',
        'action_field_id': 'theme-1', 'count': 1, 'reason': '完整题材说明', 'list': [stock()]}]}


def test_fixed_contract_units_and_unabridged_explanation():
    result = replay._parse_replay(count(), field(), DATE)
    assert set(result) == {'date', 'themes'}
    theme = result['themes'][0]
    assert set(theme) == {'name', 'reason', 'stocks'}
    item = theme['stocks'][0]
    assert set(item) == {'code', 'exchange', 'name', 'price', 'change_percent',
        'limit_up_time', 'streak_text', 'explanation'}
    assert item['price'] == 12.34 and item['change_percent'] == -1.02
    assert item['explanation'] == '第一行\n第二行\n完整解析原文'


def test_all_themes_and_stocks_preserved_in_source_order_and_same_stock_in_other_theme():
    doc = field()
    doc['data'][0]['list'].extend([stock('sz000001'), stock('bj920001')])
    doc['data'][0]['count'] = 9  # count 口径尚未核实，不能凭测试假设等于行数。
    second = deepcopy(doc['data'][0])
    second['action_field_id'] = 'theme-2'
    second['name'] = '另一题材'
    doc['data'].append(second)
    result = replay._parse_replay(count(total=4), doc, DATE)
    assert [t['name'] for t in result['themes']] == ['受控题材', '另一题材']
    assert [s['exchange'] for s in result['themes'][0]['stocks']] == ['sh', 'sz', 'bj']
    assert len(result['themes'][1]['stocks']) == 3


def test_diagram_not_exposed_and_extra_fields_ignored():
    doc = field()
    doc['data'].insert(0, {'name': '简图', 'date': DATE, 'count': 1, 'reason': '图片',
        'action_field_id': '', 'unknown': {}})
    doc['extra'] = True
    doc['data'][1]['unknown'] = True
    doc['data'][1]['list'][0]['article']['action_info']['unknown'] = {}
    assert len(replay._parse_replay(count(), doc, DATE)['themes']) == 1


@pytest.mark.parametrize('missing', [None, '', '--', '-'])
def test_missing_numbers_distinct_from_zero(missing):
    doc = field()
    info = doc['data'][0]['list'][0]['article']['action_info']
    info.update(price=0, shares_range=missing, time='', num=None, expound=None)
    item = replay._parse_replay(count(), doc, DATE)['themes'][0]['stocks'][0]
    assert item['price'] == 0 and item['change_percent'] is None
    assert item['limit_up_time'] is None and item['streak_text'] is None and item['explanation'] is None
    info.update(price=missing, shares_range=0)
    item = replay._parse_replay(count(), doc, DATE)['themes'][0]['stocks'][0]
    assert item['price'] is None and item['change_percent'] == 0


def test_missing_optional_leaves_keep_stock():
    doc = field()
    doc['data'][0].pop('reason')
    doc['data'][0]['list'][0]['article']['action_info'] = {}
    item = replay._parse_replay(count(), doc, DATE)['themes'][0]['stocks'][0]
    assert all(item[k] is None for k in ('price', 'change_percent', 'limit_up_time', 'streak_text', 'explanation'))


@pytest.mark.parametrize('code', ['600519', 'hk600519', 'sh６００５１９', 'sh12345', None, 600519, ' sh600519'])
def test_invalid_explicit_security_identity(code):
    doc = field()
    doc['data'][0]['list'][0]['code'] = code
    with pytest.raises(SourceError):
        replay._parse_replay(count(), doc, DATE)


@pytest.mark.parametrize('key,value', [
    ('price', True), ('price', -1), ('price', []), ('price', float('inf')),
    ('shares_range', False), ('shares_range', 'nan'), ('shares_range', {}),
    ('time', '24:00:00'), ('time', '09:30'), ('time', 0), ('num', 1), ('expound', []),
])
def test_known_bad_values_fail_whole_replay(key, value):
    doc = field()
    doc['data'][0]['list'][0]['article']['action_info'][key] = value
    with pytest.raises(SourceError):
        replay._parse_replay(count(), doc, DATE)


@pytest.mark.parametrize('target', ['count', 'field', 'theme', 'stock', 'article', 'info', 'theme_date'])
def test_required_structure_damage(target):
    cnt, doc = count(), field()
    if target == 'count': cnt['data'] = []
    if target == 'field': doc['data'] = {}
    if target == 'theme': doc['data'][0] = None
    if target == 'stock': doc['data'][0]['list'][0] = None
    if target == 'article': doc['data'][0]['list'][0]['article'] = None
    if target == 'info': doc['data'][0]['list'][0]['article']['action_info'] = None
    if target == 'theme_date': doc['data'][0]['date'] = '2026-09-29'
    with pytest.raises(SourceError): replay._parse_replay(cnt, doc, DATE)


@pytest.mark.parametrize('bad_count', [None, True, -1, 1.1, [], 'bad', float('nan')])
@pytest.mark.parametrize('where', ['all', 'theme'])
def test_declared_count_must_be_nonnegative_integer(bad_count, where):
    cnt, doc = count(), field()
    if where == 'all': cnt['data']['all'] = bad_count
    else: doc['data'][0]['count'] = bad_count
    with pytest.raises(SourceError): replay._parse_replay(cnt, doc, DATE)


def test_positive_counts_cannot_hide_empty_business_lists_and_zero_can_be_empty():
    with pytest.raises(SourceError): replay._parse_replay(count(), {'errCode': 0, 'data': []}, DATE)
    doc = field(); doc['data'][0]['list'] = []
    with pytest.raises(SourceError): replay._parse_replay(count(), doc, DATE)
    assert replay._parse_replay(count(total=0), {'errCode': 0, 'data': []}, DATE) == {'date': DATE, 'themes': []}


def test_duplicates_only_fail_within_same_theme_or_same_theme_identity():
    doc = field(); doc['data'][0]['list'].append(stock())
    with pytest.raises(SourceError, match='证券身份重复'): replay._parse_replay(count(), doc, DATE)
    doc = field(); doc['data'].append(deepcopy(doc['data'][0]))
    with pytest.raises(SourceError, match='题材身份重复'): replay._parse_replay(count(), doc, DATE)


@pytest.mark.parametrize('code', [1, '1', 110, '110', 500, True, None])
@pytest.mark.parametrize('side', ['count', 'field'])
def test_error_responses_fail_without_echoing_sensitive_msg(code, side):
    cnt, doc = count(), field()
    broken = {'errCode': code, 'msg': SESSION, 'data': []}
    if side == 'count': cnt = broken
    else: doc = broken
    with pytest.raises(SourceError) as caught: replay._parse_replay(cnt, doc, DATE)
    assert SESSION not in str(caught.value)


@pytest.mark.parametrize('bad_date', [True, 20260930, '', '2026-9-30', '2026-02-29', date(2026, 9, 30)])
def test_invalid_date_rejected_before_browser(monkeypatch, bad_date):
    monkeypatch.setattr(replay, '_capture', lambda *args: pytest.fail('不能请求'))
    with pytest.raises(ValueError): replay.jygs_replay(bad_date, session=SESSION, timeout=1)


@pytest.mark.parametrize('bad_session', [None, '', True, ' foo ', 'foo;bar', 'foo\nbar', 'foo,bar', 'foo\\bar', 'foo"bar'])
def test_invalid_session_rejected_without_echoing(monkeypatch, bad_session):
    monkeypatch.setattr(replay, '_capture', lambda *args: pytest.fail('不能请求'))
    with pytest.raises(ValueError) as caught: replay.jygs_replay(DATE, session=bad_session, timeout=1)
    if isinstance(bad_session, str) and bad_session: assert bad_session not in str(caught.value)


def test_latest_date_uses_official_flow_and_explicit_date_allows_official_fallback(monkeypatch):
    calls = []
    def capture(url, session, timeout):
        calls.append((url, session, timeout))
        return count(), field(), '2026-10-08', DATE
    monkeypatch.setattr(replay, '_capture', capture)
    assert replay.jygs_replay(session=SESSION, timeout=2)['date'] == DATE
    assert calls[0][0] == 'https://www.jiuyangongshe.com/action'
    assert replay.jygs_replay('2026-10-08', session=SESSION, timeout=2)['date'] == DATE
    assert calls[1][0].endswith('/action/2026-10-08')


@pytest.mark.parametrize('count_day,field_day', [('2026-10-01', DATE), (DATE, '2026-09-29'), ('2026-09-29', DATE)])
def test_request_chain_date_mismatch_is_not_normal_return(monkeypatch, count_day, field_day):
    monkeypatch.setattr(replay, '_capture', lambda *args: (count(), field(), count_day, field_day))
    with pytest.raises(SourceError): replay.jygs_replay(DATE, session=SESSION, timeout=1)


class FakeBrowser:
    def __init__(self, cnt=None, fld=None, fail=None, night=False, reorder=False):
        self.count, self.field = cnt or count(), fld or field()
        self.fail, self.night, self.reorder = fail, night, reorder
        self.handlers, self.cookies, self.urls = {}, [], []
        self.context_closed = self.browser_closed = self.runtime_closed = False
        self.clicked = False
        self.chromium = self
        self.first = self

    def __enter__(self): return self
    def __exit__(self, *args): self.runtime_closed = True
    def launch(self, **kwargs):
        if self.fail == 'launch': raise RuntimeError('secret ' + SESSION)
        return self
    def new_context(self): return self
    def add_cookies(self, cookies): self.cookies = cookies
    def new_page(self): return self
    def goto(self, url, **kwargs):
        self.urls.append(url)
        assert kwargs['wait_until'] == 'domcontentloaded'
        if self.fail == 'goto': raise RuntimeError('secret ' + SESSION)
    def on(self, event, callback): self.handlers[event] = callback
    def wait_for_function(self, expression, **kwargs):
        assert '_isMounted' in expression and kwargs['timeout'] > 0
    def get_by_text(self, text, **kwargs):
        assert text == '全部异动解析' and kwargs['exact']
        return self
    def click(self, **kwargs):
        self.clicked = True  # night 模拟只提供简图，仍必须点击官网 all。
        if self.fail == 'click': raise RuntimeError('secret ' + SESSION)
        if self.fail == 'no-response': return
        pairs = [('count-pc', self.count, '2026-10-08'), ('field', self.field, DATE)]
        if self.reorder: pairs.reverse()
        for endpoint, document, day in pairs:
            payload = {'date': day}
            if endpoint == 'field': payload['pc'] = 1
            request = SimpleNamespace(url=replay._API + endpoint, method='POST', post_data=json.dumps(payload))
            # Request 是可哈希的对象，和 Playwright wrapper 相同。
            request = Request(request.url, request.method, request.post_data)
            self.handlers['request'](request)
            response = SimpleNamespace(request=request, status=403 if self.fail == 'http' else 200,
                json=lambda document=document: document)
            self.handlers['response'](response)
    def wait_for_timeout(self, milliseconds):
        if self.fail == 'no-response': raise TimeoutError(SESSION)
    def close(self):
        if not self.context_closed: self.context_closed = True
        else: self.browser_closed = True


class Request:
    def __init__(self, url, method, post_data): self.url, self.method, self.post_data = url, method, post_data


def install_fake(monkeypatch, browser):
    monkeypatch.setattr(replay, '_load_playwright', lambda: lambda: browser)


def test_browser_click_night_chain_cookies_and_cleanup(monkeypatch):
    browser = FakeBrowser(night=True)
    install_fake(monkeypatch, browser)
    result = replay.jygs_replay(session=SESSION, timeout=2)
    assert result['date'] == DATE and browser.clicked
    assert browser.urls == ['https://www.jiuyangongshe.com/action']
    assert {c['domain'] for c in browser.cookies} == {'www.jiuyangongshe.com', 'web-api.jiuyangongshe.com'}
    assert all(c['name'] == 'SESSION' and c['value'] == SESSION for c in browser.cookies)
    assert browser.context_closed and browser.browser_closed and browser.runtime_closed
    assert SESSION not in str(result)


@pytest.mark.parametrize('failure', ['launch', 'goto', 'click', 'http', 'no-response'])
def test_browser_transport_failures_hide_credentials_and_cleanup(monkeypatch, failure):
    browser = FakeBrowser(fail=failure)
    install_fake(monkeypatch, browser)
    with pytest.raises(SourceError) as caught: replay.jygs_replay(session=SESSION, timeout=2)
    assert SESSION not in str(caught.value)
    if failure != 'http': assert caught.value.__suppress_context__
    assert browser.runtime_closed
    if failure != 'launch': assert browser.context_closed and browser.browser_closed


def test_browser_auth_rejection_does_not_wait_or_return_empty(monkeypatch):
    browser = FakeBrowser(cnt={'errCode': 110, 'msg': SESSION, 'data': []})
    install_fake(monkeypatch, browser)
    with pytest.raises(SourceError, match='110'): replay.jygs_replay(session=SESSION, timeout=2)
    assert browser.context_closed and browser.browser_closed


def test_browser_field_before_count_fails_chain(monkeypatch):
    browser = FakeBrowser(reorder=True)
    install_fake(monkeypatch, browser)
    with pytest.raises(SourceError, match='未关联'): replay.jygs_replay(session=SESSION, timeout=2)


def test_missing_dependency_is_explicit(monkeypatch):
    import builtins
    original = builtins.__import__
    def importer(name, *args, **kwargs):
        if name == 'playwright.sync_api': raise ImportError('not installed ' + SESSION)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', importer)
    with pytest.raises(SourceError, match=r'finchx\[jygs\]') as caught: replay._load_playwright()
    assert SESSION not in str(caught.value)


@pytest.mark.parametrize('timeout', [None, True, 0, -1, float('nan'), float('inf'), '3'])
def test_invalid_timeout_never_launches_browser(monkeypatch, timeout):
    monkeypatch.setattr(replay, '_capture', lambda *args: pytest.fail('不能请求'))
    with pytest.raises(ValueError): replay.jygs_replay(DATE, session=SESSION, timeout=timeout)


def test_ssr_effective_date_can_already_be_earlier_before_all_tab_click(monkeypatch):
    monkeypatch.setattr(replay, '_capture', lambda *args: (count(), field(), DATE, DATE))
    assert replay.jygs_replay('2026-10-08', session=SESSION, timeout=1)['date'] == DATE


def test_only_diagram_does_not_hide_missing_positive_business_count():
    doc = {'errCode': 0, 'data': [{'name': '简图', 'date': DATE, 'count': 1}]}
    with pytest.raises(SourceError, match='未提供题材'): replay._parse_replay(count(), doc, DATE)


def test_empty_themes_do_not_hide_positive_all_count():
    doc = field()
    doc['data'][0].update(count=0, list=[])
    with pytest.raises(SourceError, match='未提供题材'):
        replay._parse_replay(count(total=1), doc, DATE)
    # 来源确认为零时，允许保留来源的空题材。
    result = replay._parse_replay(count(total=0), doc, DATE)
    assert result['themes'][0]['stocks'] == []


def test_browser_missing_chromium_reports_prepare_step_and_closes_runtime(monkeypatch):
    browser = FakeBrowser()
    def launch(**kwargs): raise RuntimeError("Executable doesn't exist at /temporary/browser " + SESSION)
    browser.launch = launch
    install_fake(monkeypatch, browser)
    with pytest.raises(SourceError, match='playwright install chromium') as caught:
        replay.jygs_replay(session=SESSION, timeout=2)
    assert SESSION not in str(caught.value) and browser.runtime_closed


def test_browser_null_json_response_is_malformed_not_timeout(monkeypatch):
    browser = FakeBrowser(); browser.count = None
    install_fake(monkeypatch, browser)
    with pytest.raises(SourceError, match='响应不是对象'): replay.jygs_replay(session=SESSION, timeout=2)


def test_capture_ignores_navigation_requests_that_precede_all_click(monkeypatch):
    browser = FakeBrowser()
    original = browser.goto
    def goto(url, **kwargs):
        original(url, **kwargs)
        assert not browser.handlers  # 初始/SSR链不能混入点击后的链。
    browser.goto = goto
    install_fake(monkeypatch, browser)
    assert replay.jygs_replay(session=SESSION, timeout=2)['date'] == DATE


def test_session_is_fresh_per_call_and_not_cached(monkeypatch):
    calls = []
    def capture(url, session, timeout):
        calls.append(session)
        return count(), field(), DATE, DATE
    monkeypatch.setattr(replay, '_capture', capture)
    replay.jygs_replay(DATE, session=SESSION, timeout=1)
    replay.jygs_replay(DATE, session='different-session', timeout=1)
    assert calls == [SESSION, 'different-session']


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_normalize_browser_path_and_requested_day(monkeypatch, value):
    calls = []
    def capture(url, session, seconds):
        calls.append(url)
        return count(), field(), DATE, DATE
    monkeypatch.setattr(replay, "_capture", capture)
    from finchx import FinchX
    result = FinchX().fupan.jygs_replay(value, session=SESSION)
    assert result["date"] == DATE
    assert calls == ["https://www.jiuyangongshe.com/action/2026-09-30"]
