"""显式重新累计日的场景边界；模拟输入不充当联网示例。"""
from copy import deepcopy
from datetime import date, datetime
import inspect
import warnings

import pytest

from finchx import FinchX, SourceError
from test_deviation import serve, assert_shape, SCENE


def test_reset_none_and_old_reset_preserve_values_warnings_and_calls(monkeypatch):
    state = serve(monkeypatch)
    api = FinchX().regulation
    with warnings.catch_warnings(record=True) as recorded:
        original = api.deviation('600519')
        calls = deepcopy(state['calls'])
        state['calls'].clear()
        assert api.deviation('600519', reset_date=None) == original
        assert state['calls'] == calls
        state['calls'].clear()
        assert api.deviation('600519', reset_date='2026-09-01') == original
        assert state['calls'] == calls
    assert not recorded
    assert_shape(original)
    assert inspect.signature(api.deviation).parameters['reset_date'].kind == inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        api.deviation('600519', (10, 30), None, '2026-10-07')


@pytest.mark.parametrize('reset', ['2026-10-07', '20261007', '2026/10/07',
    '2026-10-07 12:34:56', '20261007 12:34:56', '2026/10/07 12:34:56'])
def test_reset_six_formats_clip_all_scenes_and_keep_same_baseline(monkeypatch, reset):
    serve(monkeypatch)
    result = FinchX().regulation.deviation('600519', reset_date=reset)
    assert_shape(result)
    assert result['coverage_status'] == 'complete'
    for row in result['windows']:
        assert row['available_trading_days'] == row['trading_days'] == 2
        assert row['start_date'] == '2026-10-07'
        assert row['stock_baseline_date'] == row['benchmark_baseline_date'] == '2026-10-06'
        assert row['window_status'] == 'partial_after_reset'
        assert row['threshold_percent'] == (100 if row['window_days'] == 10 else 200)


@pytest.mark.parametrize('reset', [date(2026, 10, 7), datetime(2026, 10, 7), True,
    20261007, '', ' 2026-10-07', '2026-10-07 ', '2026-10-07 12:34',
    '2026-10-07T12:34:56', '2026-10-07 12:34:56.0', '2026-10-07 25:00:00',
    '2026-02-30', '２０２６１００７'])
def test_reset_rejects_invalid_parameter_before_any_requests(monkeypatch, reset):
    state = serve(monkeypatch)
    with pytest.raises(ValueError):
        FinchX().regulation.deviation('600519', reset_date=reset)
    assert state['calls'] == []


def test_reset_does_not_roll_back_nontrading_day(monkeypatch):
    state = serve(monkeypatch)
    state['calendar_change'] = lambda rows: [row.update(is_trading_day=False)
        for row in rows if row['date'] == '2026-10-07']
    with pytest.raises(ValueError, match='reset_date'):
        FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert not any(call[0] == 'daily' for call in state['calls'])


def test_reset_outside_calendar_uses_only_one_extra_day_check(monkeypatch):
    state = serve(monkeypatch)
    api = FinchX().regulation
    expected = api.deviation('600519')
    state['calls'].clear()
    assert api.deviation('600519', reset_date='1990-01-02') == expected
    calendars = [call for call in state['calls'] if call[0] == 'calendar']
    assert len(calendars) == 2
    assert calendars[1][1:3] == (date(1990, 1, 2), date(1990, 1, 2))


@pytest.mark.parametrize('reset', ['1990-01-02', '2026-10-07'])
def test_reset_calendar_damage_is_source_error(monkeypatch, reset):
    state = serve(monkeypatch)
    state['calendar_change'] = lambda rows: [row.pop('is_trading_day')
        for row in rows if row['date'] == reset]
    with pytest.raises(SourceError):
        FinchX().regulation.deviation('600519', reset_date=reset)


@pytest.mark.parametrize('historical', [False, True])
@pytest.mark.parametrize('basis', ['qfq', 'raw', None])
def test_reset_first_day_uses_real_two_points_and_actual_basis(monkeypatch, historical, basis):
    state = serve(monkeypatch)
    state['actual_adjustment'] = basis
    observed = '2026-09-30' if historical else '2026-10-08'
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter('always')
        result = FinchX().regulation.deviation('600519', end_date=observed, reset_date=observed)
    for row in result['windows']:
        assert row['available_trading_days'] == row['trading_days'] == 1
        assert row['start_date'] == observed
        assert row['window_start_price'] == row['stock_price']
        assert row['window_status'] == 'partial_after_reset'
        assert row['deviation_percent'] == row['stock_change_percent']
        assert row['benchmark_change_percent'] == 0
    assert result['price_basis'] == ('qfq_stock_anchored_to_price_date__raw_index'
        if basis == 'qfq' else 'raw_stock__raw_index')
    assert len(recorded) == (1 if basis is None else 0)
    daily = [call for call in state['calls'] if call[0] == 'daily']
    assert len(daily) == (3 if historical and basis == 'qfq' else 2)


@pytest.mark.parametrize('historical', [False, True])
def test_future_reset_zero_keeps_current_and_real_terminal_baselines(monkeypatch, historical):
    serve(monkeypatch)
    observed, next_date = ('2026-09-30', '2026-10-01') if historical else ('2026-10-08', '2026-10-09')
    api = FinchX().regulation
    original = api.deviation('600519', end_date=observed)
    result = api.deviation('600519', end_date=observed, reset_date=next_date)
    assert result['coverage_status'] == original['coverage_status']
    for before, row in zip(original['windows'], result['windows']):
        assert set(row) == SCENE
        if row['scenario'] == 'current':
            assert row == before
            continue
        assert row['window_status'] == 'reset_not_started'
        assert row['available_trading_days'] == row['trading_days'] == 0
        assert row['price_date'] == row['stock_baseline_date'] == row['benchmark_baseline_date'] == observed
        assert row['target_date'] == row['start_date'] == next_date
        assert row['stock_baseline_price'] == row['stock_price'] == before['stock_price']
        assert row['benchmark_baseline_level'] == row['benchmark_level'] == before['benchmark_level']
        assert all(row[field] is None for field in ('window_start_price', 'stock_change_percent',
            'benchmark_change_percent', 'deviation_percent'))
        assert row['theoretical_trigger_price'] == row['stock_price'] * (2 if row['window_days'] == 10 else 3)
        assert row['remaining_change_percent'] == pytest.approx((row['trigger_price'] / row['stock_price'] - 1) * 100)


def test_reset_later_than_next_session_leaves_both_scenes_unchanged(monkeypatch):
    state = serve(monkeypatch)
    api = FinchX().regulation
    original = api.deviation('600519')
    calls = deepcopy(state['calls'])
    state['calls'].clear()
    assert api.deviation('600519', reset_date='2026-10-10') == original
    assert state['calls'] == calls


@pytest.mark.parametrize('window', [10, 30])
@pytest.mark.parametrize('offset', [0, 1, 2, 9, 10, 29, 30])
def test_rolling_window_boundaries_and_reset_exits_window(monkeypatch, window, offset):
    from datetime import timedelta
    serve(monkeypatch)
    api = FinchX().regulation
    original = api.deviation('600519', windows=(window,))
    reset = (date(2026, 10, 8) - timedelta(days=offset)).isoformat()
    result = api.deviation('600519', windows=(window,), reset_date=reset)
    for before, row in zip(original['windows'], result['windows']):
        normal_count = window - (row['scenario'] == 'next_session')
        assert row['available_trading_days'] == min(offset + 1, normal_count)
        if offset + 1 >= normal_count:
            assert row == before
        else:
            assert row['window_status'] == 'partial_after_reset'
            assert row['start_date'] >= reset


@pytest.mark.parametrize('field', ['qfq', 'index'])
def test_unneeded_pre_reset_missing_prices_do_not_fail_or_warn(monkeypatch, field):
    state = serve(monkeypatch)
    state[field] = [row for row in state[field] if row['date'] != '2026-09-20']
    with warnings.catch_warnings(record=True) as recorded:
        result = FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert not recorded
    assert result['inferred_halt_dates'] == []
    assert result['coverage_status'] == 'complete'


def test_received_old_bad_row_cannot_be_hidden_by_reset(monkeypatch):
    state = serve(monkeypatch)
    # 缺少必要基准触发整份扩取；唯一旧行不参与 reset 统计，但仍须校验。
    state['actual_adjustment'] = None
    state['qfq'] = [row for row in state['qfq'] if row['date'] != '2026-10-06']
    for row in state['qfq']:
        if row['date'] == '2026-09-20':
            row['close'] = float('nan')
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter('always')
        with pytest.raises(SourceError, match='stock.close 必须是有限数字'):
            FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert len([call for call in state['calls'] if call[0] == 'daily']) == 3
    assert not recorded


def test_reset_gap_then_resume_retains_halt_status_and_warns_once(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] != '2026-10-07']
    with pytest.warns(UserWarning, match='2026-10-07') as recorded:
        result = FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert len(recorded) == 1
    assert result['coverage_status'] == 'halt_inferred_from_missing_kline'
    for row in result['windows']:
        assert row['window_status'] == 'partial_after_inferred_halt'
        assert row['start_date'] == '2026-10-08'
        assert row['stock_baseline_date'] == '2026-10-06'
        assert row['benchmark_baseline_date'] == '2026-10-07'
        assert row['available_trading_days'] == 1


def test_missing_reset_baseline_expands_stock_and_uses_last_real_price(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] not in ('2026-10-05', '2026-10-06')]
    with pytest.warns(UserWarning):
        result = FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert len([call for call in state['calls'] if call[0] == 'daily']) == 3
    for row in result['windows']:
        assert row['start_date'] == '2026-10-07'
        assert row['stock_baseline_date'] == '2026-10-04'
        assert row['benchmark_baseline_date'] == '2026-10-06'
        assert row['window_status'] == 'partial_after_inferred_halt'


@pytest.mark.parametrize('missing', ['2026-10-06', '2026-10-07'])
def test_reset_required_index_missing_fails_without_success_warning(monkeypatch, missing):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    state['index'] = [row for row in state['index'] if row['date'] != missing]
    with warnings.catch_warnings(record=True) as recorded:
        with pytest.raises(SourceError):
            FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert not recorded


def test_reset_listing_prefix_preserves_coverage_reason(monkeypatch):
    state = serve(monkeypatch)
    state['listing'] = date(2026, 10, 6)
    state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-10-06']
    result = FinchX().regulation.deviation('600519', reset_date='2026-10-06')
    assert result['coverage_status'] == 'short_history'
    assert all(row['window_status'] == 'partial_short_history' for row in result['windows'])
    assert all(row['available_trading_days'] == 2 for row in result['windows'])


def test_reset_raw_warning_filter_error_preserves_userwarning(monkeypatch):
    state = serve(monkeypatch)
    state['actual_adjustment'] = None
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        with pytest.raises(UserWarning):
            FinchX().regulation.deviation('600519', reset_date='2026-10-07')


@pytest.mark.parametrize('basis', ['qfq', None])
@pytest.mark.parametrize('historical', [False, True])
def test_explicit_none_preserves_halt_raw_warning_order_and_calls(monkeypatch, basis, historical):
    state = serve(monkeypatch)
    state['actual_adjustment'] = basis
    state['qfq'] = [row for row in state['qfq'] if row['date'] != '2026-09-25']
    api = FinchX().regulation
    args = {'end_date': '2026-09-30'} if historical else {}
    with warnings.catch_warnings(record=True) as original_warnings:
        warnings.simplefilter('always')
        original = api.deviation('600519', **args)
    calls = deepcopy(state['calls'])
    state['calls'].clear()
    with warnings.catch_warnings(record=True) as none_warnings:
        warnings.simplefilter('always')
        actual = api.deviation('600519', reset_date=None, **args)
    assert actual == original
    assert state['calls'] == calls
    assert [(item.category, str(item.message)) for item in none_warnings] == [
        (item.category, str(item.message)) for item in original_warnings]


def test_future_zero_trigger_rounds_up_and_preserves_real_quote(monkeypatch):
    state = serve(monkeypatch)
    state['stock_quote']['price'] = 1.0001
    result = FinchX().regulation.deviation('600519', reset_date='2026-10-09')
    rows = [row for row in result['windows'] if row['scenario'] == 'next_session']
    assert [(row['theoretical_trigger_price'], row['trigger_price']) for row in rows] == [
        (2.0002, 2.01), (3.0003, 3.01)]
    assert all(row['stock_price'] == row['stock_baseline_price'] == 1.0001 for row in rows)


def test_reset_unknown_missing_baseline_is_not_short_history(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] >= '2026-10-07']
    with warnings.catch_warnings(record=True) as recorded:
        with pytest.raises(SourceError, match='上市边界'):
            FinchX().regulation.deviation('600519', reset_date='2026-10-07')
    assert not recorded


def test_reset_halt_warning_error_is_not_wrapped(monkeypatch):
    state = serve(monkeypatch)
    state['qfq'] = [row for row in state['qfq'] if row['date'] != '2026-10-07']
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        with pytest.raises(UserWarning, match='停牌'):
            FinchX().regulation.deviation('600519', reset_date='2026-10-07')
