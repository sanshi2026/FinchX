"""偏离计算的业务契约及故障边界；人工序列仅用于明确模拟的数学测试。"""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect
import warnings

import pytest

from finchx import FinchX, SourceError
from finchx._common.deviation import calculate_window

TOP = {'code', 'exchange', 'board', 'end_date', 'benchmark', 'price_basis', 'coverage_status', 'inferred_halt_dates', 'windows'}
SCENE = {'window_days', 'scenario', 'price_date', 'target_date', 'available_trading_days', 'window_status', 'coverage_status', 'stock_price', 'benchmark_level', 'stock_price_type', 'benchmark_value_type', 'stock_time', 'benchmark_time', 'start_date', 'stock_baseline_date', 'benchmark_baseline_date', 'inferred_halt_dates', 'trading_days', 'stock_baseline_price', 'window_start_price', 'benchmark_baseline_level', 'stock_change_percent', 'benchmark_change_percent', 'deviation_percent', 'threshold_percent', 'theoretical_trigger_price', 'trigger_price', 'remaining_change_percent'}


def math_window(stock_values, index_values, *, scenario='current', window=10, scale='1', terminal=None):
    sessions = [date(2026, 1, 1) + timedelta(days=i) for i in range(len(stock_values))]
    stock = dict(zip(sessions, map(Decimal, map(str, stock_values))))
    index = dict(zip(sessions, map(Decimal, map(str, index_values))))
    return calculate_window(stock, index, sessions, window_days=window, scenario=scenario,
        target_date=sessions[-1] + timedelta(days=scenario == 'next_session'),
        stock_price=Decimal(str(terminal)) if terminal is not None else stock[sessions[-1]] * Decimal(scale),
        benchmark_level=index[sessions[-1]], scale=Decimal(scale), coverage_status='complete',
        stock_time=None, benchmark_time=None)


@pytest.mark.parametrize('scenario', ['current', 'next_session'])
def test_trigger_uses_maximum_baseline_instead_of_lowest_candidate_price(scenario):
    result = math_window([10, 100, 50, 30], [10, 100, 50, 100], scenario=scenario)
    assert result['stock_baseline_date'] == '2026-01-02'
    assert result['start_date'] == '2026-01-03'
    assert result['stock_baseline_price'] == 100
    assert result['window_start_price'] == 50
    assert result['deviation_percent'] == pytest.approx(-70)
    # 最早候选可得到110，但其偏离更小；不能借用它的低触发价。
    assert result['theoretical_trigger_price'] == 200
    assert result['trigger_price'] == 200
    assert result['remaining_change_percent'] == pytest.approx((200 / 30 - 1) * 100)


@pytest.mark.parametrize('scenario', ['current', 'next_session'])
@pytest.mark.parametrize('window,trigger,remaining', [(10, 40, -20), (30, 50, 0)])
def test_trigger_formula_uses_selected_stock_and_index_baselines(scenario, window, trigger, remaining):
    result = math_window([100, 10, 30, 50], [100, 50, 80, 150], scenario=scenario, window=window)
    assert result['stock_baseline_date'] == '2026-01-02'
    assert result['stock_baseline_price'] == 10
    assert result['window_start_price'] == 30
    assert result['benchmark_baseline_level'] == 50
    assert result['deviation_percent'] == 200
    assert result['threshold_percent'] == (100 if window == 10 else 200)
    assert result['theoretical_trigger_price'] == trigger
    assert result['trigger_price'] == trigger
    assert result['remaining_change_percent'] == remaining


def test_candidate_boundary_excludes_one_day_current_but_keeps_next_session():
    prices = [100] * 10 + [1000]
    current = math_window(prices, [100] * 11)
    assert current['trading_days'] == 10
    # next_session has a shifted boundary and N points, so maximum may use one day.
    next_row = math_window([100] * 8 + [10, 1000], [100] * 10, scenario='next_session')
    assert next_row['trading_days'] == 1
    assert current['available_trading_days'] == 10
    assert next_row['available_trading_days'] == 9
    assert current['window_status'] == next_row['window_status'] == 'complete'


def test_ties_choose_earliest_candidate_and_preserve_zero():
    result = math_window([10] * 11, [100] * 11)
    assert result['start_date'] == '2026-01-02'
    assert result['deviation_percent'] == 0
    assert result['stock_change_percent'] == 0
    assert result['threshold_percent'] == 100
    assert math_window([10] * 31, [100] * 31, window=30)['threshold_percent'] == 200


@pytest.mark.parametrize('baseline,theoretical,rounded,remaining', [
    ('1', 2, 2, 100),
    ('1.0001', 2.0002, 2.01, 101),
    ('1.005', 2.01, 2.01, 101),
])
def test_round_up_after_selection_and_remaining_uses_rounded_price(baseline, theoretical, rounded, remaining):
    result = math_window([baseline, '1.5', '1'], [100, 100, 100])
    assert result['theoretical_trigger_price'] == theoretical
    assert result['trigger_price'] == rounded
    assert result['remaining_change_percent'] == remaining


@pytest.mark.parametrize('scenario', ['current', 'next_session'])
def test_tied_deviation_keeps_earliest_baseline_even_when_later_trigger_is_lower(scenario):
    result = math_window([12, 6, 999, 12], [60, 40, 1, 120], scenario=scenario)
    assert result['deviation_percent'] == -100
    assert result['stock_baseline_date'] == '2026-01-01'
    assert result['start_date'] == '2026-01-02'
    assert result['theoretical_trigger_price'] == result['trigger_price'] == 36


def test_non_one_price_anchor_preserves_returns_and_scales_all_stock_prices():
    base = math_window([10, 100, 50, 30], [10, 100, 50, 100])
    scaled = math_window([10, 100, 50, 30], [10, 100, 50, 100], scale='2')
    assert scaled['deviation_percent'] == base['deviation_percent']
    assert scaled['stock_price'] == 60
    assert scaled['stock_baseline_price'] == 200
    assert scaled['window_start_price'] == 100
    assert scaled['trigger_price'] == 400


def test_two_point_short_history_special_case():
    result = math_window([10, 20], [100, 100])
    assert result['trading_days'] == 1
    assert result['window_status'] == 'partial_short_history'
    assert result['deviation_percent'] == 100


def test_latest_single_day_winner_start_price_is_quote_not_stale_daily_bar():
    result = math_window([100] * 8 + [10, 999], [100] * 10,
                         scenario='next_session', terminal=1000)
    assert result['start_date'] == result['price_date']
    assert result['trading_days'] == 1
    assert result['window_start_price'] == result['stock_price'] == 1000


def serve(monkeypatch):
    """明确模拟连续交易日与来源业务输出，不作为文档真实示例。"""
    from finchx.sources.tencent import deviation as source
    from finchx.api.reference import ReferenceAPI
    days = [date(2026, 8, 1) + timedelta(days=i) for i in range(69)]
    state = {'calls': [], 'qfq': [{'date': day.isoformat(), 'close': 10 + i} for i, day in enumerate(days)],
        'index': [{'date': day.isoformat(), 'close': 100} for day in days],
        'stock_quote': {'code': '600519', 'exchange': 'sh', 'time': '2026-10-08T16:14:57+08:00', 'price': 160, 'previous_close': 154},
        'index_quote': {'code': '000002', 'exchange': 'sh', 'time': '2026-10-08T16:15:00+08:00', 'price': 100},
        'listing': date(1980, 1, 1), 'calendar_change': None, 'actual_adjustment': 'qfq'}
    monkeypatch.setattr(source, '_now', lambda: datetime(2026, 10, 8, 16, 30, tzinfo=timezone(timedelta(hours=8))))
    def quotes(code, *, kind='stock', timeout):
        state['calls'].append(('quote', code, kind, timeout))
        return deepcopy(state['index_quote'] if kind == 'index' else state['stock_quote'])
    def klines(code, start_date, end_date, adjust=None, *, kind='stock', timeout):
        state['calls'].append(('daily', code, kind, adjust, timeout))
        rows = state['index'] if kind == 'index' else state['qfq']
        result = [deepcopy(row) for row in rows if start_date.isoformat() <= row['date'] <= end_date.isoformat()]
        if kind == 'stock' and adjust is None:
            for row in result:
                row['close'] *= 2
        return result
    def calendar(self, start, end, *, source='auto'):
        state['calls'].append(('calendar', start, end, self._timeout))
        rows = [{'date': (start + timedelta(days=i)).isoformat(), 'is_trading_day': True} for i in range((end-start).days+1)]
        if state['calendar_change']:
            state['calendar_change'](rows)
        return rows
    def listing(code, *, timeout):
        state['calls'].append(('listing', code, timeout))
        return state['listing']
    monkeypatch.setattr(source.quote, 'quote_snapshot', quotes)
    monkeypatch.setattr(source.klines, 'ohlcv', klines)
    monkeypatch.setattr(source.klines, '_ohlcv_with_basis', lambda *args, **kwargs: (
        klines(*args, **kwargs), state['actual_adjustment'],
    ))
    monkeypatch.setattr(source, '_listing_date', listing)
    monkeypatch.setattr(ReferenceAPI, 'trading_calendar', calendar)
    return state


def assert_shape(result):
    assert set(result) == TOP
    assert set(result['benchmark']) == {'code', 'exchange', 'name'}
    assert result['inferred_halt_dates'] == []
    for row in result['windows']:
        assert set(row) == SCENE
        assert len(row) == 28
        assert row['stock_baseline_date'] == row['benchmark_baseline_date']
        assert row['inferred_halt_dates'] == []


def test_public_default_shape_order_real_named_fields_and_no_preopen(monkeypatch):
    state = serve(monkeypatch)
    api = FinchX(timeout=2.5).regulation
    result = api.deviation('600519')
    assert_shape(result)
    assert [(row['window_days'], row['scenario']) for row in result['windows']] == [(10, 'current'), (10, 'next_session'), (30, 'current'), (30, 'next_session')]
    assert result['end_date'] == '2026-10-08'
    assert result['price_basis'] == 'qfq_stock_anchored_to_price_date__raw_index'
    assert result['benchmark'] == {'code': '000002', 'exchange': 'sh', 'name': '上证A指'}
    assert all(row['stock_price_type'] == row['benchmark_value_type'] == 'quote' for row in result['windows'])
    assert all(row['stock_time'] == '2026-10-08T16:14:57+08:00' for row in result['windows'])
    assert all(row['benchmark_time'] == '2026-10-08T16:15:00+08:00' for row in result['windows'])
    assert all(row['stock_price'] == 160 for row in result['windows'])
    assert len([call for call in state['calls'] if call[0] == 'daily']) == 2
    assert all(call[-1] == 2.5 for call in state['calls'])
    assert not hasattr(FinchX().market, 'deviation')
    assert list(inspect.signature(api.deviation).parameters) == ['code', 'windows', 'end_date', 'reset_date']


def test_historical_raw_anchor_and_input_window_order_share_source_calls(monkeypatch):
    state = serve(monkeypatch)
    result = FinchX().regulation.deviation('600519', windows=[30, 10], end_date='2026-09-30')
    assert_shape(result)
    assert [(row['window_days'], row['scenario']) for row in result['windows']] == [(30, 'current'), (30, 'next_session'), (10, 'current'), (10, 'next_session')]
    assert len([call for call in state['calls'] if call[0] == 'daily']) == 3
    assert len([call for call in state['calls'] if call[0] == 'calendar']) == 1
    row = result['windows'][0]
    assert row['stock_price_type'] == 'daily_close'
    assert row['stock_time'] is row['benchmark_time'] is None
    qfq = {item['date']: item['close'] for item in state['qfq']}
    assert row['stock_baseline_price'] == qfq[row['stock_baseline_date']] * 2
    assert row['window_start_price'] == qfq[row['start_date']] * 2
    expected = (qfq['2026-09-30'] / qfq[row['stock_baseline_date']] - 1) * 100
    assert row['stock_change_percent'] == pytest.approx(expected)


def test_latest_quote_wins_over_daily_and_non_one_previous_close_bridge(monkeypatch):
    state = serve(monkeypatch)
    for row in state['qfq']:
        if row['date'] == '2026-10-07': row['close'] = 10
        if row['date'] == '2026-10-08': row['close'] = 999
    state['stock_quote'].update(price=1000, previous_close=20)
    result = FinchX().regulation.deviation('600519', windows=(10,))
    row = result['windows'][1]
    assert row['trading_days'] == 1
    assert row['stock_baseline_price'] == 20
    assert row['window_start_price'] == row['stock_price'] == 1000
    assert row['stock_change_percent'] == 4900


def test_latest_no_daily_today_bar_still_uses_verified_quotes(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] != '2026-10-08']
    state['index'] = [row for row in state['index'] if row['date'] != '2026-10-08']
    result = FinchX().regulation.deviation('600519')
    assert all(row['window_status'] == 'complete' for row in result['windows'])
    assert all(row['stock_price'] == 160 for row in result['windows'])


@pytest.mark.parametrize('code', [600519, True, None, '６００５１９', 'sh600519', '60051', '830001', '510300', '000002 '])
def test_invalid_code_fails_before_requests(monkeypatch, code):
    state = serve(monkeypatch)
    with pytest.raises(ValueError): FinchX().regulation.deviation(code)
    assert not state['calls']


@pytest.mark.parametrize('windows', [None, True, [], (), [True], [10, 10], [30, 30], [5], [10.0], {10}, '10'])
def test_invalid_windows_fail_before_requests(monkeypatch, windows):
    state = serve(monkeypatch)
    with pytest.raises(ValueError): FinchX().regulation.deviation('600519', windows=windows)
    assert not state['calls']


@pytest.mark.parametrize('end', ['', '2026-02-30', True, date(2026, 9, 30), '2026-09-30T00:00:00'])
def test_invalid_date_fails_before_requests(monkeypatch, end):
    state = serve(monkeypatch)
    with pytest.raises(ValueError): FinchX().regulation.deviation('600519', end_date=end)
    assert not state['calls']


def test_future_observation_is_value_error_and_calendar_closed_day_rolls_back(monkeypatch):
    state = serve(monkeypatch)
    with pytest.raises(ValueError): FinchX().regulation.deviation('600519', end_date='2026-10-09')
    def closed(rows):
        for row in rows:
            if row['date'] in {'2026-10-09', '2026-10-10'}: row['is_trading_day'] = False
    state['calendar_change'] = closed
    result = FinchX().regulation.deviation('600519', end_date='2026-10-10')
    assert result['end_date'] == '2026-10-08'
    assert result['windows'][1]['target_date'] == '2026-10-11'


@pytest.mark.parametrize('field,value', [('price', 0), ('price', -1), ('price', True), ('price', float('nan')), ('price', float('inf')), ('price', None), ('previous_close', 0), ('previous_close', None), ('time', None), ('time', '2026-10-08T08:00:00+08:00'), ('time', '2026-10-08T16:15:00'), ('time', '2026-10-08T18:00:00+08:00'), ('code', '600000'), ('exchange', 'sz')])
def test_known_quote_corruption_fails_whole_request(monkeypatch, field, value):
    state = serve(monkeypatch)
    state['stock_quote'][field] = value
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


@pytest.mark.parametrize('value', [0, -1, True, None, float('nan'), float('inf')])
def test_required_daily_nonpositive_and_nonfinite_close_fail(monkeypatch, value):
    state = serve(monkeypatch)
    state['qfq'][-5]['close'] = value
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


@pytest.mark.parametrize('stream', ['qfq', 'index'])
def test_duplicate_daily_fails_and_only_stock_interior_gap_is_inferred(monkeypatch, stream):
    state = serve(monkeypatch)
    state[stream].append(deepcopy(state[stream][-4]))
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')
    state[stream] = [row for row in state[stream] if row['date'] != '2026-10-05']
    if stream == 'index':
        with pytest.raises(SourceError): FinchX().regulation.deviation('600519')
    else:
        with pytest.warns(UserWarning, match='未核对交易所停牌公告'):
            result = FinchX().regulation.deviation('600519')
        assert result['inferred_halt_dates'] == ['2026-10-05']


def test_short_listing_requires_true_boundary_and_preserves_row_coverage(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = state['qfq'][-3:]
    state['listing'] = date(2026, 10, 6)
    result = FinchX().regulation.deviation('600519')
    assert result['coverage_status'] == 'short_history'
    assert all(row['coverage_status'] == 'short_history' and row['window_status'] == 'partial_short_history' for row in result['windows'])
    state['listing'] = date(2026, 10, 5)
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_short_history_two_points_allowed_one_point_fails_whole_result(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = state['qfq'][-2:]
    state['listing'] = date(2026, 10, 7)
    result = FinchX().regulation.deviation('600519')
    assert all(row['trading_days'] == 1 for row in result['windows'])
    state['qfq'] = state['qfq'][-1:]
    state['listing'] = date(2026, 10, 8)
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_calendar_corruption_never_guesses_weekdays(monkeypatch):
    state = serve(monkeypatch)
    for change in [lambda rows: rows.pop(), lambda rows: rows.append(deepcopy(rows[0])), lambda rows: rows[0].update(is_trading_day=1), lambda rows: [row.update(is_trading_day=False) for row in rows]]:
        state['calendar_change'] = change
        with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_each_call_fetches_again_and_preserves_unknown_extra_fields(monkeypatch):
    state = serve(monkeypatch)
    state['stock_quote']['unknown'] = {'malformed': True}
    result = FinchX().regulation.deviation('600519')
    count = len(state['calls'])
    assert FinchX().regulation.deviation('600519') == result
    assert len(state['calls']) == count * 2


def test_cross_date_quotes_fail_after_bounded_pair_retry(monkeypatch):
    state = serve(monkeypatch)
    state['stock_quote']['time'] = '2026-10-07T16:14:57+08:00'
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')
    assert len([call for call in state['calls'] if call[0] == 'quote']) == 5
    assert not any(call[0] == 'daily' for call in state['calls'])


def test_old_source_date_cannot_define_latest_when_calendar_has_new_started_session(monkeypatch):
    state = serve(monkeypatch)
    state['stock_quote']['time'] = '2026-10-07T16:14:57+08:00'
    state['index_quote']['time'] = '2026-10-07T16:15:00+08:00'
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_latest_closed_session_requires_late_session_quote(monkeypatch):
    state = serve(monkeypatch)
    state['stock_quote']['time'] = '2026-10-08T12:15:00+08:00'
    state['index_quote']['time'] = '2026-10-08T12:15:00+08:00'
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


@pytest.mark.parametrize('clock,stamp', [('10:30','09:45'),('12:00','11:10')])
def test_intraday_and_lunch_quote_freshness(monkeypatch, clock, stamp):
    from finchx.sources.tencent import deviation as source
    state = serve(monkeypatch)
    monkeypatch.setattr(source, '_now', lambda: datetime.fromisoformat('2026-10-08T'+clock+':00+08:00'))
    state['stock_quote']['time'] = state['index_quote']['time'] = '2026-10-08T'+stamp+':00+08:00'
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_daily_bar_on_explicit_calendar_closed_day_is_source_error(monkeypatch):
    state = serve(monkeypatch)
    def closed(rows):
        for row in rows:
            if row['date'] == '2026-09-30': row['is_trading_day'] = False
    state['calendar_change'] = closed
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_before_open_keeps_prior_confirmed_closed_session(monkeypatch):
    from finchx.sources.tencent import deviation as source
    state = serve(monkeypatch)
    monkeypatch.setattr(source, '_now', lambda: datetime.fromisoformat('2026-10-09T09:00:00+08:00'))
    result = FinchX().regulation.deviation('600519')
    assert result['end_date'] == '2026-10-08'
    assert result['windows'][1]['target_date'] == '2026-10-09'
    assert result['windows'][0]['stock_time'] == state['stock_quote']['time']


def test_closed_days_keep_prior_source_session_only_with_confirmed_calendar(monkeypatch):
    from finchx.sources.tencent import deviation as source
    state = serve(monkeypatch)
    monkeypatch.setattr(source, '_now', lambda: datetime.fromisoformat('2026-10-10T16:00:00+08:00'))
    def closed(rows):
        for row in rows:
            if row['date'] in {'2026-10-09', '2026-10-10'}: row['is_trading_day'] = False
    state['calendar_change'] = closed
    result = FinchX().regulation.deviation('600519')
    assert result['end_date'] == '2026-10-08'
    assert result['windows'][1]['target_date'] == '2026-10-11'
    state['stock_quote']['time'] = '2026-10-08T14:00:00+08:00'
    with pytest.raises(SourceError): FinchX().regulation.deviation('600519')


def test_listing_boundary_reads_real_profile_without_unrelated_financial_parse(monkeypatch):
    import json
    from pathlib import Path
    from finchx.sources.tencent import deviation as source
    payload = json.loads((Path(__file__).parent / 'fixtures' / 'company_sh600519_f10.txt').read_text(encoding="utf-8"))
    payload['data']['zyzb'] = False  # 明确模拟无关业务块损坏，不影响必要上市边界。
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return json.dumps(payload)
    monkeypatch.setattr(source, 'get_text', request)
    assert source._listing_date('600519', timeout=2.5) == date(2001, 8, 27)
    assert calls[0][1]['timeout'] == 2.5
    assert 'code=sh600519' in calls[0][0]
    for comparison in [None, False, {}, {'stock': {'stockcode': '600000', 'sc': 'sz'}}, {'stock': []}]:
        payload['data']['hydb'] = comparison
        assert source._listing_date('600519', timeout=2.5) == date(2001, 8, 27)
    payload['data'].pop('hydb')
    assert source._listing_date('600519', timeout=2.5) == date(2001, 8, 27)
    for invalid in [None, '2001/08/27', '2001-02-30', True]:
        payload['data']['gsjj']['riqi'] = invalid
        with pytest.raises(SourceError): source._listing_date('600519', timeout=2.5)
    for profile in [None, False, []]:
        payload['data']['gsjj'] = profile
        with pytest.raises(SourceError): source._listing_date('600519', timeout=2.5)


def test_trigger_remaining_zero_and_negative_are_business_values():
    zero = math_window([10] * 10 + [20], [100] * 11)
    negative = math_window([10] * 10 + [100], [100] * 11)
    assert zero['remaining_change_percent'] == 0
    assert negative['remaining_change_percent'] == -80


@pytest.mark.parametrize("value", ['2026-09-30', '20260930', '2026/09/30', '2026-09-30 15:30:00', '20260930 15:30:00', '2026/09/30 15:30:00'])
def test_all_date_string_formats_select_same_observation_day(monkeypatch, value):
    serve(monkeypatch)
    result = FinchX().regulation.deviation("600519", end_date=value)
    assert result["end_date"] == "2026-09-30"


def remove_stock(state, *dates):
    state['qfq'] = [row for row in state['qfq'] if row['date'] not in dates]


def test_halt_replay_600825_uses_two_baselines_and_same_maximum_trigger():
    """2.0.3价格离线重放；9/25..27显式不在fixture交易日里，不验证官方日历。"""
    base = date(2026, 9, 4)
    index_base = date(2026, 9, 18)
    resumed = [date(2026, 9, day) for day in (21, 22, 23, 24, 28)]
    stock = dict(zip([base] + resumed, map(Decimal, ['5.31', '5.84', '6.42', '7.06', '7.77', '8.55'])))
    index = {index_base: Decimal('4101.66'), **{day: Decimal('4101.66') for day in resumed}}
    index[resumed[-1]] = Decimal('4008.96')
    result = calculate_window(stock, index, [index_base] + resumed,
        window_days=10, scenario='current', target_date=resumed[-1],
        stock_price=stock[resumed[-1]], benchmark_level=index[resumed[-1]], scale=Decimal(1),
        coverage_status='halt_inferred_from_missing_kline', stock_time=None, benchmark_time=None,
        first_baselines=(base, index_base), inferred_halt_dates=(index_base,))
    assert result['stock_baseline_date'] == '2026-09-04'
    assert result['benchmark_baseline_date'] == '2026-09-18'
    assert result['start_date'] == '2026-09-21'
    assert result['window_start_price'] == 5.84
    assert result['deviation_percent'] == pytest.approx(63.2770097134)
    assert result['trigger_price'] == 10.50
    assert result['available_trading_days'] == result['trading_days'] == 5


def test_live_first_resume_day_bridges_last_actual_stock_not_previous_market_day(monkeypatch):
    state = serve(monkeypatch)
    dates = [date(2026, 9, 30) + timedelta(days=i) for i in range(8)]
    remove_stock(state, *(day.isoformat() for day in dates))
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519', windows=(10,))
    assert len(caught) == 1
    message = str(caught[0].message)
    assert '股票日线缺口推定为停牌' in message and '未核对交易所停牌公告' in message
    assert '2026-09-30' in message and '2026-10-07' in message
    assert '10日窗口/当前场景' in message and '次一交易日场景' in message and '可用统计日1天' in message
    for row in result['windows']:
        assert row['stock_baseline_date'] == '2026-09-29'
        assert row['benchmark_baseline_date'] == '2026-10-07'
        assert row['stock_baseline_price'] == 154
        assert row['window_start_price'] == row['stock_price'] == 160
        assert row['available_trading_days'] == row['trading_days'] == 1
        assert row['window_status'] == 'partial_after_inferred_halt'
        assert row['stock_change_percent'] == pytest.approx((160 / 154 - 1) * 100)


def test_multiple_gaps_are_reported_but_only_last_resume_segment_is_scanned(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-20', '2026-10-03', '2026-10-04', '2026-10-05')
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519')
    assert len(caught) == 1
    assert result['inferred_halt_dates'] == ['2026-09-20', '2026-10-03', '2026-10-04', '2026-10-05']
    for row in result['windows']:
        assert row['start_date'] == '2026-10-06'
        assert row['stock_baseline_date'] == '2026-10-02'
        assert row['benchmark_baseline_date'] == '2026-10-05'
        assert row['available_trading_days'] == 3
        assert row['inferred_halt_dates'] == (result['inferred_halt_dates'] if row['window_days'] == 30 else result['inferred_halt_dates'][1:])


def test_only_thirty_day_rows_affected_and_normal_ten_day_rows_preserved(monkeypatch):
    state = serve(monkeypatch)
    original = FinchX().regulation.deviation('600519')
    remove_stock(state, '2026-09-15')
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519')
    assert result['windows'][:2] == original['windows'][:2]
    assert all(row['inferred_halt_dates'] == ['2026-09-15'] for row in result['windows'][2:])
    assert '10日窗口' not in str(caught[0].message)
    assert result['coverage_status'] == 'halt_inferred_from_missing_kline'


def test_gap_crossing_requested_history_boundary_uses_one_bounded_full_qfq_refetch(monkeypatch):
    state = serve(monkeypatch)
    dates = [date(2026, 9, 15) + timedelta(days=i) for i in range(18)]
    remove_stock(state, *(day.isoformat() for day in dates))
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519', windows=(10,))
    assert len([call for call in state['calls'] if call[0] == 'daily' and call[3] == 'qfq']) == 2
    assert not any(call[0] == 'listing' for call in state['calls'])
    row = result['windows'][0]
    assert row['stock_baseline_date'] == '2026-09-14'
    assert row['benchmark_baseline_date'] == '2026-10-02'
    assert row['start_date'] == '2026-10-03'
    assert row['inferred_halt_dates'] == ['2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02']
    assert result['windows'][1]['inferred_halt_dates'] == row['inferred_halt_dates'][1:]


def test_listing_short_history_and_internal_halts_remain_independent(monkeypatch):
    state = serve(monkeypatch)
    state['listing'] = date(2026, 9, 20)
    state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-09-20']
    remove_stock(state, '2026-09-25', '2026-10-05')
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519')
    assert result['coverage_status'] == 'short_history_and_halt_inferred_from_missing_kline'
    for row in result['windows']:
        assert row['available_trading_days'] == 3
        if row['window_days'] == 30:
            assert row['coverage_status'] == 'short_history_and_halt_inferred_from_missing_kline'
            assert row['window_status'] == 'partial_short_history_and_inferred_halt'
        else:
            assert row['coverage_status'] == 'halt_inferred_from_missing_kline'
            assert row['window_status'] == 'partial_after_inferred_halt'


@pytest.mark.parametrize('broken', ['no_stock_anchor', 'bad_expanded_anchor', 'index_gap_before_last_halt', 'index_resume_baseline'])
def test_halt_cannot_hide_missing_or_corrupt_necessary_inputs_and_never_warns_on_failure(monkeypatch, broken):
    state = serve(monkeypatch)
    remove_stock(state, '2026-10-05')
    if broken == 'no_stock_anchor':
        state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-10-06']
    elif broken == 'bad_expanded_anchor':
        remove_stock(state, *[(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(35)])
        state['qfq'][20]['close'] = 0
    else:
        missing = '2026-09-20' if broken == 'index_gap_before_last_halt' else '2026-10-05'
        state['index'] = [row for row in state['index'] if row['date'] != missing]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        with pytest.raises(SourceError): FinchX().regulation.deviation('600519')
    assert not caught


def test_later_window_failure_does_not_emit_success_warning(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-10-06']
    state['listing'] = date(2026, 10, 6)
    remove_stock(state, '2026-10-07')
    from finchx.sources.tencent import deviation as source
    original = source.calculate_window
    def calculation(*args, **kwargs):
        if kwargs['window_days'] == 30:
            raise SourceError('deviation', '明确模拟后窗口计算失败')
        return original(*args, **kwargs)
    monkeypatch.setattr(source, 'calculate_window', calculation)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        with pytest.raises(SourceError): FinchX().regulation.deviation('600519')
    assert not caught


@pytest.mark.parametrize('action', ['ignore', 'error'])
def test_inferred_halt_warning_obeys_standard_filters(monkeypatch, action):
    state = serve(monkeypatch)
    remove_stock(state, '2026-10-05')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter(action, UserWarning)
        if action == 'error':
            with pytest.raises(UserWarning, match='2026-10-05'):
                FinchX().regulation.deviation('600519')
        else:
            result = FinchX().regulation.deviation('600519')
            assert result['inferred_halt_dates'] == ['2026-10-05']
        assert not caught


def test_historical_missing_observation_is_not_inferred_halt(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-30')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        with pytest.raises(SourceError):
            FinchX().regulation.deviation('600519', end_date='2026-09-30')
    assert not caught


def test_calendar_closed_day_does_not_become_halt(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-10-05')
    state['index'] = [row for row in state['index'] if row['date'] != '2026-10-05']
    state['calendar_change'] = lambda rows: [row.update(is_trading_day=False) for row in rows if row['date'] == '2026-10-05']
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = FinchX().regulation.deviation('600519')
    assert not caught
    assert result['coverage_status'] == 'complete'
    assert result['inferred_halt_dates'] == []


def test_halt_on_current_baseline_day_has_full_available_window_and_next_unaffected(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-28')
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519', windows=(10,))
    current, following = result['windows']
    assert current['inferred_halt_dates'] == ['2026-09-28']
    assert current['available_trading_days'] == 10
    assert current['window_status'] == 'complete'
    assert current['stock_baseline_date'] == '2026-09-27'
    assert current['benchmark_baseline_date'] == '2026-09-28'
    assert following['coverage_status'] == following['window_status'] == 'complete'
    assert following['inferred_halt_dates'] == []
    assert '次一交易日' not in str(caught[0].message)
    assert '窗口不足' not in str(caught[0].message)


def test_first_response_calendar_conflict_is_not_hidden_by_clean_expanded_response(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-27', '2026-09-28')
    state['calendar_change'] = lambda rows: [row.update(is_trading_day=False) for row in rows if row['date'] == '2026-10-05']
    state['index'] = [row for row in state['index'] if row['date'] != '2026-10-05']
    from finchx.sources.tencent import deviation as source
    original = source.klines._ohlcv_with_basis
    qfq_reads = []
    def klines(code, start_date, end_date, adjust=None, *, kind='stock', timeout):
        result, basis = original(code, start_date, end_date, adjust, kind=kind, timeout=timeout)
        if adjust == 'qfq':
            qfq_reads.append(start_date)
            if len(qfq_reads) > 1:
                result = [row for row in result if row['date'] != '2026-10-05']
        return result, basis
    monkeypatch.setattr(source.klines, '_ohlcv_with_basis', klines)
    with pytest.raises(SourceError, match='非交易标记冲突'):
        FinchX().regulation.deviation('600519', windows=(10,))
    assert qfq_reads == [date(2026, 9, 27)]
    assert not any(row['date'] == '2026-09-27' for row in state['qfq'])


def test_expanded_response_is_validated_and_supplies_single_qfq_scale(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-28')
    from finchx.sources.tencent import deviation as source
    original = source.klines._ohlcv_with_basis
    reads = []
    def klines(code, start_date, end_date, adjust=None, *, kind='stock', timeout):
        result, basis = original(code, start_date, end_date, adjust, kind=kind, timeout=timeout)
        if adjust == 'qfq':
            reads.append(start_date)
            if len(reads) == 1:
                for row in result:
                    row['close'] *= 100
        return result, basis
    monkeypatch.setattr(source.klines, '_ohlcv_with_basis', klines)
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519', windows=(10,))
    prices = {row['date']: row['close'] for row in state['qfq']}
    current = result['windows'][0]
    assert current['stock_baseline_price'] == pytest.approx(prices['2026-09-27'] * 154 / prices['2026-10-07'])
    assert current['window_start_price'] == pytest.approx(prices['2026-09-29'] * 154 / prices['2026-10-07'])
    assert len(reads) == 2


def test_halt_later_maximum_candidate_uses_common_resumed_baseline_and_its_trigger():
    base, index_base = date(2026, 1, 1), date(2026, 1, 3)
    resumed = [date(2026, 1, day) for day in (4, 5, 6)]
    stock = dict(zip([base] + resumed, map(Decimal, [100, 200, 30, 30])))
    index = dict(zip([index_base] + resumed, map(Decimal, [50, 100, 100, 100])))
    result = calculate_window(stock, index, [index_base] + resumed,
        window_days=10, scenario='current', target_date=resumed[-1],
        stock_price=stock[resumed[-1]], benchmark_level=index[resumed[-1]], scale=Decimal(1),
        coverage_status='halt_inferred_from_missing_kline', stock_time=None, benchmark_time=None,
        first_baselines=(base, index_base), inferred_halt_dates=(index_base,))
    assert result['stock_baseline_date'] == result['benchmark_baseline_date'] == '2026-01-04'
    assert result['start_date'] == '2026-01-05'
    assert result['window_start_price'] == 30
    assert result['deviation_percent'] == -85
    # 首复牌候选的触发价300更低，但本次最大偏离候选仍必须使用400。
    assert result['theoretical_trigger_price'] == result['trigger_price'] == 400


def test_historical_halt_still_anchors_every_stock_price_to_raw_terminal_close(monkeypatch):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-26', '2026-09-27')
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519', windows=(10,), end_date='2026-09-30')
    row = result['windows'][0]
    qfq = {item['date']: item['close'] for item in state['qfq']}
    assert row['stock_price'] == qfq['2026-09-30'] * 2
    assert row['stock_baseline_date'] == '2026-09-25'
    assert row['benchmark_baseline_date'] == '2026-09-27'
    assert row['stock_baseline_price'] == qfq['2026-09-25'] * 2
    assert row['window_start_price'] == qfq['2026-09-28'] * 2
    assert row['stock_time'] is row['benchmark_time'] is None
    assert row['stock_price_type'] == 'daily_close'
    assert row['stock_change_percent'] == pytest.approx((qfq['2026-09-30'] / qfq['2026-09-25'] - 1) * 100)


def test_index_missing_only_before_confirmed_listing_does_not_reject_valid_ipo_and_halt(monkeypatch):
    state = serve(monkeypatch)
    state['listing'] = date(2026, 10, 6)
    state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-10-06']
    state['index'] = [row for row in state['index'] if row['date'] >= '2026-10-06']
    remove_stock(state, '2026-10-07')
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519')
    assert result['coverage_status'] == 'short_history_and_halt_inferred_from_missing_kline'
    assert all(row['stock_baseline_date'] == '2026-10-06' and row['benchmark_baseline_date'] == '2026-10-07' for row in result['windows'])


@pytest.mark.parametrize('previous_close', [1, 1000000, None, 0, True])
def test_raw_latest_uses_actual_quotes_and_ignores_previous_close_bridge(monkeypatch, previous_close):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    state['stock_quote']['previous_close'] = previous_close
    state['qfq'][-1]['close'] = 999  # 最新日线旧值不替代真实报价。
    with pytest.warns(UserWarning, match='近似当作无需复权') as caught:
        result = FinchX(timeout=2.5).regulation.deviation('600519')
    assert len(caught) == 1
    assert_shape(result)
    assert result['price_basis'] == 'raw_stock__raw_index'
    prices = {row['date']: row['close'] for row in state['qfq']}
    for row in result['windows']:
        assert row['stock_price'] == 160
        assert row['stock_baseline_price'] == prices[row['stock_baseline_date']]
        assert row['window_start_price'] == (160 if row['start_date'] == '2026-10-08' else prices[row['start_date']])
        assert row['stock_change_percent'] == pytest.approx((160 / prices[row['stock_baseline_date']] - 1) * 100)
    assert len([call for call in state['calls'] if call[0] == 'daily']) == 2


def test_raw_historical_reuses_observed_close_without_extra_raw_request(monkeypatch):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519', end_date='2026-09-30')
    assert len(caught) == 1
    assert_shape(result)
    assert result['price_basis'] == 'raw_stock__raw_index'
    prices = {row['date']: row['close'] for row in state['qfq']}
    for row in result['windows']:
        assert row['stock_price'] == prices['2026-09-30']
        assert row['stock_baseline_price'] == prices[row['stock_baseline_date']]
        assert row['window_start_price'] == prices[row['start_date']]
        assert row['stock_time'] is row['benchmark_time'] is None
    assert [call[2:4] for call in state['calls'] if call[0] == 'daily'] == [('stock', 'qfq'), ('index', None)]


@pytest.mark.parametrize('end_date', [None, '2026-10-07'])
def test_raw_confirmed_listing_short_history_keeps_shape_and_one_warning_after_refetch(monkeypatch, end_date):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    state['listing'] = date(2026, 10, 6)
    state['qfq'] = state['qfq'][-3:]
    with pytest.warns(UserWarning, match='不复权') as caught:
        result = FinchX().regulation.deviation('600519', end_date=end_date)
    assert len(caught) == 1
    assert_shape(result)
    assert result['coverage_status'] == 'short_history'
    assert all(row['window_status'] == 'partial_short_history' for row in result['windows'])
    assert len([call for call in state['calls'] if call[0] == 'daily' and call[3] == 'qfq']) == 2
    assert len([call for call in state['calls'] if call[0] == 'listing']) == 1


@pytest.mark.parametrize('short_history', [False, True])
def test_raw_halt_keeps_two_baselines_and_independent_listing_status(monkeypatch, short_history):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    if short_history:
        state['listing'] = date(2026, 10, 6)
        state['qfq'] = state['qfq'][-3:]
    remove_stock(state, '2026-10-07')
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519')
    assert len(caught) == 2
    assert sum('近似当作无需复权' in str(item.message) for item in caught) == 1
    assert result['coverage_status'] == ('short_history_and_halt_inferred_from_missing_kline' if short_history else 'halt_inferred_from_missing_kline')
    base = next(row['close'] for row in state['qfq'] if row['date'] == '2026-10-06')
    for row in result['windows']:
        assert row['stock_baseline_date'] == '2026-10-06'
        assert row['benchmark_baseline_date'] == '2026-10-07'
        assert row['stock_baseline_price'] == base
        assert row['stock_price'] == row['window_start_price'] == 160
        assert row['available_trading_days'] == 1
        assert row['stock_change_percent'] == pytest.approx((160 / base - 1) * 100)


@pytest.mark.parametrize('broken', ['one_point', 'bad_price', 'index_gap', 'missing_observation', 'bad_listing', 'later_window'])
def test_raw_failure_keeps_source_error_and_never_emits_success_warning(monkeypatch, broken):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    kwargs = {}
    if broken == 'one_point':
        state['qfq'] = state['qfq'][-1:]
        state['listing'] = date(2026, 10, 8)
    elif broken == 'bad_price':
        state['qfq'][-5]['close'] = 0
    elif broken == 'index_gap':
        state['index'] = state['index'][:-4]
    elif broken == 'missing_observation':
        remove_stock(state, '2026-09-30')
        kwargs['end_date'] = '2026-09-30'
    elif broken == 'bad_listing':
        state['qfq'] = state['qfq'][-3:]
        state['listing'] = date(2026, 10, 5)
    else:
        from finchx.sources.tencent import deviation as source
        original = source.calculate_window
        def calculation(*args, **kwargs):
            if kwargs['window_days'] == 30:
                raise SourceError('deviation', '明确模拟后窗口失败')
            return original(*args, **kwargs)
        monkeypatch.setattr(source, 'calculate_window', calculation)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        with pytest.raises(SourceError):
            FinchX().regulation.deviation('600519', **kwargs)
    assert not caught


@pytest.mark.parametrize('action', ['ignore', 'error'])
def test_raw_warning_keeps_standard_python_filter_behavior(monkeypatch, action):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter(action, UserWarning)
        if action == 'error':
            with pytest.raises(UserWarning, match='不复权'):
                FinchX().regulation.deviation('600519')
        else:
            assert FinchX().regulation.deviation('600519')['price_basis'] == 'raw_stock__raw_index'
    assert not caught


@pytest.mark.parametrize('final_basis', [None, 'qfq'])
def test_expanded_full_response_replaces_price_basis_without_mixing_or_duplicate_warning(monkeypatch, final_basis):
    state = serve(monkeypatch)
    remove_stock(state, '2026-09-28')
    from finchx.sources.tencent import deviation as source
    original = source.klines._ohlcv_with_basis
    reads = []
    def with_basis(*args, **kwargs):
        rows, _ = original(*args, **kwargs)
        reads.append(args[1])
        if len(reads) == 1:
            for row in rows:
                row['close'] *= 100
        return rows, final_basis if len(reads) > 1 else ('qfq' if final_basis is None else None)
    monkeypatch.setattr(source.klines, '_ohlcv_with_basis', with_basis)
    with pytest.warns(UserWarning) as caught:
        result = FinchX().regulation.deviation('600519', windows=(10,))
    assert len(reads) == 2
    assert len(caught) == (2 if final_basis is None else 1)
    assert result['price_basis'] == ('raw_stock__raw_index' if final_basis is None else 'qfq_stock_anchored_to_price_date__raw_index')
    prices = {row['date']: row['close'] for row in state['qfq']}
    scale = 1 if final_basis is None else 154 / prices['2026-10-07']
    row = result['windows'][0]
    assert row['stock_baseline_price'] == pytest.approx(prices[row['stock_baseline_date']] * scale)
