"""监管业务及全量分页契约；fixtures 为真实响应，分页变异明确模拟。"""

from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from finchx import FinchX, SourceError
from finchx.sources.eastmoney import regulation

_FIXTURES = Path(__file__).parent / "fixtures"
_FIELDS = {
    "watchlist":{"code","exchange","name","monitor_start_date","expected_end_date","source_url"},
    "abnormal_records":{"code","exchange","name","event_type","start_date","end_date","announcement_date","announcement_id","reason","reason_type","monitor_start_date","monitor_end_date","monitor_status"},
    "abnormal_prediction_history":{"code","exchange","name","date","change_percent","window_days","deviation_percent","trigger_change_percent","is_triggered","rule","direction","is_current"},
    "severe_predictions":{"code","exchange","name","date","board","rule","window_days","deviation_percent","trigger_change_percent","change_percent","scenario","is_triggered"},
    "abnormal_counts":{"code","exchange","name","date","price","change_percent","abnormal_count","max_deviation_percent"},
}


def fixture(name):
    return json.loads((_FIXTURES / f"regulation_{name}.json").read_text(encoding="utf-8"))


def serve(monkeypatch, overrides=None, page_hook=None):
    """DC fixture 仅节选真实业务行，计数按本次模拟集合重设，非真实全量实返。"""
    calls=[]; overridden=overrides or {}
    def request(url,**kwargs):
        query=parse_qs(urlsplit(url).query);path=urlsplit(url).path
        if 'stock_monitor.json' in path:key='watchlist'
        elif path.endswith('/list'):key='predictions'
        elif path.endswith('/count'):key='counts'
        elif query.get('reportName')==['RPT_WATCH_UNUSUAL_FLUCTUATE']:key='history'
        else:key='severe' if '002' in query.get('filter',[''])[0] else 'ordinary'
        data=deepcopy(overridden.get(key,fixture(key)))
        page=int(query.get('pageNumber',query.get('pageNo',['1']))[0]);size=int(query.get('pageSize',['200'])[0])
        calls.append((key,page,query,kwargs))
        if key!='watchlist':
            block=data['result'] if isinstance(data['result'],dict) else data
            rows=block['data'];block['count']=len(rows);block['pages']=math.ceil(len(rows)/size)
            block['data']=rows[(page-1)*size:page*size]
        if page_hook is not None:data=page_hook(key,page,query,data)
        return data
    monkeypatch.setattr(regulation.http,'get_json',request)
    return calls


def test_watchlist_preserves_etf_northern_stocks_optional_dates_and_source_links(monkeypatch):
    calls=serve(monkeypatch);api=FinchX(timeout=20).regulation
    rows=api.watchlist(); source=fixture('watchlist')
    assert len(rows)==len(source)==14 and all(set(row)==_FIELDS['watchlist'] for row in rows)
    assert {row['code'] for row in rows}=={row['STKCODE'] for row in source}
    etf=next(row for row in rows if row['code']=='159509')
    assert etf=={'code':'159509','exchange':'sz','name':'纳指科技','monitor_start_date':'2026-09-30','expected_end_date':'2026-10-20','source_url':'https://wap.18.cn/app/detail/818/3349'}
    assert next(row for row in rows if row['code']=='920575')['exchange']=='bj'
    assert all(kwargs['timeout']==20 for key,page,q,kwargs in calls)
    assert api.watchlist()==rows and len(calls)==2


def test_two_announcement_types_share_resource_but_preserve_current_history_records(monkeypatch):
    calls=serve(monkeypatch);api=FinchX().regulation
    ordinary=api.abnormal_records();severe=api.abnormal_records('severe')
    assert len(ordinary)==len(fixture('ordinary')['result']['data']) and len(severe)==8
    assert all(set(row)==_FIELDS['abnormal_records'] for row in ordinary+severe)
    assert all(row['event_type']=='ordinary' and row['monitor_start_date'] is row['monitor_end_date'] is row['monitor_status'] is None for row in ordinary)
    first=next(row for row in severe if row['announcement_id']=='AN202610071830184946')
    assert first['code']=='688137' and first['start_date']=='2026-09-16' and first['end_date']=='2026-09-30'
    assert first['announcement_date']=='2026-10-08' and first['monitor_start_date']=='2026-10-08' and first['monitor_end_date']=='2026-10-21'
    assert {row['monitor_status'] for row in severe}=={'current','history'}
    assert any(row['exchange']=='bj' for row in severe)
    assert next(row for row in ordinary if row['code']=='200521')['exchange']=='sz'
    assert next(row for row in ordinary if row['code']=='900939')['exchange']=='sh'
    assert all(q['reportName']==['RPT_APP_UNUSUALBASIC'] for key,page,q,kwargs in calls)
    assert '001' in calls[0][2]['filter'][0] and '002' in calls[1][2]['filter'][0]
    assert all(len(q['sortColumns'][0].split(','))>=3 for key,page,q,kwargs in calls)


def test_prediction_history_retains_negative_direction_current_mark_and_multiple_rules(monkeypatch):
    data=fixture('history');source=data['result']['data']
    other=deepcopy(source[0]);other.update({'UNUSUAL_TYPE':'连续三十个交易日内日收盘价涨跌幅偏离值累计达到+200%','MAX_DAYS':30,'IS_SYSDATE':'0'});source.append(other)
    serve(monkeypatch,{'history':data});rows=FinchX().regulation.abnormal_prediction_history()
    assert len(rows)==9 and all(set(row)==_FIELDS['abnormal_prediction_history'] for row in rows)
    down=next(row for row in rows if row['code']=='920025')
    assert down['direction']=='down' and down['deviation_percent']==-50.72 and down['trigger_change_percent']==-20.52
    assert down['window_days']==5 and down['is_triggered'] is False and down['is_current'] is True
    same=[row for row in rows if row['code']=='688265'];assert len(same)==2 and {row['is_current'] for row in same}=={True,False}
    assert any(row['change_percent']==-5.95567867036 for row in same)


def test_severe_predictions_keep_current_next_scenarios_north_board_and_model_states(monkeypatch):
    calls=serve(monkeypatch);rows=FinchX().regulation.severe_predictions()
    assert len(rows)==13 and all(set(row)==_FIELDS['severe_predictions'] for row in rows)
    northern=[row for row in rows if row['code']=='920025'];assert len(northern)==2
    assert all(row['exchange']=='bj' and row['board']=='bse' and row['date']=='2026-10-08' for row in northern)
    assert {row['scenario'] for row in northern}=={'current','next_session'}
    assert next(row for row in northern if row['scenario']=='next_session')['is_triggered'] is None
    assert next(row for row in northern if row['scenario']=='current')['is_triggered'] is False
    assert next(row for row in rows if row['code']=='301190')['is_triggered'] is True
    assert calls[0][2]['showBJS']==['1'] and calls[0][2]['riseOnly']==['0']


def test_counts_real_zero_negative_percent_missing_numbers_are_not_filtered(monkeypatch):
    data=fixture('counts');data['data'][1].update({'p':None,'a':'0','x':None})
    serve(monkeypatch,{'counts':data});rows=FinchX().regulation.abnormal_counts()
    assert len(rows)==15 and all(set(row)==_FIELDS['abnormal_counts'] for row in rows)
    first=next(row for row in rows if row['code']=='600825');assert first['price']==11.39 and first['max_deviation_percent']==0.0 and first['abnormal_count']==3
    missing=next(row for row in rows if row['code']=='000504');assert missing['price'] is None and missing['change_percent']==0.0 and missing['max_deviation_percent'] is None
    assert next(row for row in rows if row['code']=='000678')['change_percent']==-5.04


def test_missing_event_dates_cannot_be_replaced_with_announcement_or_monitor_dates(monkeypatch):
    data=fixture('severe');data['result']['data'][0].update({'START_DATE':None,'END_DATE':None})
    serve(monkeypatch,{'severe':data});rows=FinchX().regulation.abnormal_records('severe')
    row=next(row for row in rows if row['announcement_id']=='AN202610071830184946')
    assert row['start_date'] is row['end_date'] is None and row['announcement_date']=='2026-10-08'


@pytest.mark.parametrize('method,key,field,value',[
    ('watchlist','watchlist','MARKET','?'),('watchlist','watchlist','STKCODE','９２０５７５'),
    ('abnormal_records','ordinary','UNUSUAL_TYPE','999'),('abnormal_records','ordinary','INFO_CODE',None),
    ('abnormal_prediction_history','history','IS_POSITIVE','2'),('abnormal_prediction_history','history','IS_HAPPEN','2'),
    ('abnormal_prediction_history','history','IS_SYSDATE','2'),('abnormal_prediction_history','history','CHANGE_RATE',True),
    ('abnormal_prediction_history','history','CHANGE_RATE',False),
    ('severe_predictions','predictions','s',99),('severe_predictions','predictions','e',99),
    ('severe_predictions','predictions','o',99),('severe_predictions','predictions','m',99),
    ('abnormal_counts','counts','t',1.5),('abnormal_counts','counts','p',-1),('abnormal_counts','counts','x','nan'),
])
def test_required_identity_enums_and_known_numeric_corruption_fail_whole_result(monkeypatch,method,key,field,value):
    data=fixture(key);rows=data if isinstance(data,list) else data['result']['data'] if isinstance(data['result'],dict) else data['data']
    rows[0][field]=value;serve(monkeypatch,{key:data})
    with pytest.raises(SourceError):getattr(FinchX().regulation,method)()


def test_public_signatures_invalid_event_before_network_and_no_old_aliases(monkeypatch):
    calls=serve(monkeypatch);api=FinchX().regulation
    assert list(inspect.signature(api.abnormal_records).parameters)==['event_type']
    assert inspect.signature(api.abnormal_records).parameters['event_type'].default=='ordinary'
    for method in ['watchlist','abnormal_prediction_history','severe_predictions','abnormal_counts']:
        assert list(inspect.signature(getattr(api,method)).parameters)==[]
    for invalid in [None,True,'severe_current','ordinary ']:
        with pytest.raises(ValueError):api.abnormal_records(invalid)
    assert calls==[]
    for name in ['severe_records','monitor_list','prediction_history']:
        assert not hasattr(api,name)


@pytest.mark.parametrize('method,key,changed_field,changed_value,output_field',[
    ('abnormal_records','ordinary','UNUSUAL_REASON','后读完整公告记录','reason'),
    ('abnormal_prediction_history','history','DEVUATION_VALUE',-123.45,'deviation_percent'),
    ('severe_predictions','predictions','t',-12.34,'trigger_change_percent'),
    ('abnormal_counts','counts','p',50.25,'price'),
])
def test_cross_page_overlap_is_updated_and_completely_refilled_instead_of_partial(monkeypatch,method,key,changed_field,changed_value,output_field):
    monkeypatch.setattr(regulation,'PAGE_SIZE',2)
    fixture_data=fixture(key);block=fixture_data['result'] if isinstance(fixture_data['result'],dict) else fixture_data
    raw=deepcopy(block['data'][:3]);block['data']=raw
    later=deepcopy(raw[0]);later[changed_field]=changed_value
    name_field='SECURITY_NAME_ABBR' if key in ['ordinary','history'] else 'n';later[name_field]='后读证券名称'
    rounds=0
    def overlap(resource,page,query,data):
        nonlocal rounds
        if page==1:rounds+=1
        target=data['result'] if isinstance(data['result'],dict) else data
        if rounds==1 and page==2:target['data']=[deepcopy(later)]
        elif rounds>=2:target['data']=deepcopy([raw[1],raw[2]] if page==1 else [later])
        if isinstance(data['result'],dict):data['version']=f'每页不同hash-{rounds}-{page}'
        return data
    calls=serve(monkeypatch,{key:fixture_data},overlap)
    rows=getattr(FinchX().regulation,method)()
    assert len(rows)==3 and 2 < len(calls) <= 6
    newest=next(row for row in rows if row['name']=='后读证券名称')
    assert newest[output_field]==changed_value
    if key in ['ordinary','history']:
        assert all(len(q['sortColumns'][0].split(','))>=3 for resource,page,q,kwargs in calls)


@pytest.mark.parametrize('mode',['same_page_duplicate','short_page','total_drift','date_drift','never_complete','invalid_second_page'])
def test_pagination_corruption_or_unfilled_count_never_returns_partial(monkeypatch,mode):
    monkeypatch.setattr(regulation,'PAGE_SIZE',2)
    data=fixture('counts');rows=deepcopy(data['data'][:3]);data['data']=rows
    def corrupt(key,page,query,response):
        if mode=='same_page_duplicate' and page==1:response['data']=[deepcopy(rows[0]),deepcopy(rows[0])]
        elif mode=='short_page' and page==1:response['data']=response['data'][:1]
        elif mode=='total_drift' and page==2:response['count']=4;response['data']=[deepcopy(rows[2]),deepcopy(rows[0])]
        elif mode=='date_drift' and page==2:response['date']=20261009
        elif mode=='never_complete' and page==2:response['data']=[deepcopy(rows[0])]
        elif mode=='invalid_second_page' and page==2:response['data'][0]['c']='坏代码'
        return response
    serve(monkeypatch,{'counts':data},corrupt)
    with pytest.raises(SourceError):FinchX().regulation.abnormal_counts()


def test_watchlist_same_identity_duplicate_and_source_status_or_structure_errors_fail(monkeypatch):
    data=fixture('watchlist');data.append(deepcopy(data[0]));serve(monkeypatch,{'watchlist':data})
    with pytest.raises(SourceError):FinchX().regulation.watchlist()
    for key,method in [('ordinary','abnormal_records'),('history','abnormal_prediction_history'),('predictions','severe_predictions'),('counts','abnormal_counts')]:
        def wrong_status(resource,page,query,data):
            if resource in ['ordinary','history']:data['success']=False
            else:data['result']=1
            return data
        serve(monkeypatch,page_hook=wrong_status)
        with pytest.raises(SourceError):getattr(FinchX().regulation,method)()


def test_unknown_extra_fields_do_not_change_valid_business_results(monkeypatch):
    serve(monkeypatch);before=FinchX().regulation.severe_predictions()
    data=fixture('predictions');data['unknown']={};data['data'][0]['unknown_numeric']=['不解析额外字段']
    serve(monkeypatch,{'predictions':data})
    assert FinchX().regulation.severe_predictions()==before


def test_optional_history_flags_and_numbers_preserve_missing_separately_from_zero(monkeypatch):
    data=fixture('history');data['result']['data'][0].update({'MAX_DAYS':'0','IS_HAPPEN':None,'IS_POSITIVE':None,'IS_SYSDATE':None,'CHANGE_RATE':None,'CHANGE_RATE_TARGET':'0'})
    serve(monkeypatch,{'history':data})
    row=next(row for row in FinchX().regulation.abnormal_prediction_history() if row['code']=='688265')
    assert row['window_days']==0 and row['trigger_change_percent']==0.0
    assert row['is_triggered'] is row['direction'] is row['is_current'] is row['change_percent'] is None


def test_watchlist_same_security_different_monitor_windows_are_distinct_business_records(monkeypatch):
    data=fixture('watchlist');earlier=deepcopy(data[0])
    earlier.update({'VALIDATESTARTDATE':'2026-09-01','VALIDATEENDDATE':'2026-09-30'})
    data.append(earlier);serve(monkeypatch,{'watchlist':data})
    rows=FinchX().regulation.watchlist()
    intervals=[row for row in rows if row['code']=='920575']
    assert len(rows)==15 and len(intervals)==2
    assert {(row['monitor_start_date'],row['expected_end_date']) for row in intervals}=={('2026-10-08','2026-10-09'),('2026-09-01','2026-09-30')}


@pytest.mark.parametrize('code,bad_rule',[('301190',1),('688175',40)])
def test_prediction_rule_must_match_board_and_unverified_raw_rule_codes_fail(monkeypatch,code,bad_rule):
    data=fixture('predictions');next(row for row in data['data'] if row['c']==code)['e']=bad_rule
    serve(monkeypatch,{'predictions':data})
    with pytest.raises(SourceError):FinchX().regulation.severe_predictions()
