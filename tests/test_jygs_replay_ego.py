import json
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from finchx import FinchX
from finchx._common.errors import SourceError
from finchx.sources.jiuyangongshe import replay, replay_ego


def _run_node_script(node, script):
    with tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as output:
        subprocess.run([node, '--input-type=module', '--eval', script], text=True,
                       encoding='utf-8', stdout=output, stderr=subprocess.STDOUT,
                       check=True, timeout=5)
        output.seek(0)
        return output.read()


def test_public_forward(monkeypatch):
    marker = object()
    monkeypatch.setattr(replay_ego, 'jygs_replay_ego', lambda date, timeout: (date, timeout, marker))
    assert FinchX(timeout=7).fupan.jygs_replay_ego('2026-10-30') == ('2026-10-30', 7, marker)


def test_capture_and_parser(monkeypatch):
    date = '2026-10-30'
    records = [
        {'endpoint': replay._API + 'count-pc', 'method': 'POST', 'status': 200,
         'post': json.dumps({'date': date}), 'body': json.dumps({'errCode': 0, 'data': {'date': date, 'all': 0}})},
        {'endpoint': replay._API + 'field', 'method': 'POST', 'status': 200,
         'post': json.dumps({'date': date, 'pc': 1}), 'body': json.dumps({'errCode': 0, 'data': []})},
    ]
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='', stderr='FINCHX_RESULT=' + json.dumps(records)))
    assert replay_ego.jygs_replay_ego(date, timeout=2) == {'date': date, 'themes': []}
    records[1]['post'] = json.dumps({'date': '2026-10-29', 'pc': 1})
    with pytest.raises(SourceError, match='未关联'):
        replay_ego.jygs_replay_ego(date, timeout=2)


def test_safe_cli_failures(monkeypatch):
    for error in (FileNotFoundError(), subprocess.TimeoutExpired('ego-browser', 1), subprocess.CalledProcessError(1, 'ego-browser', stderr='secret')):
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(subprocess, 'run', fail)
        with pytest.raises(SourceError) as caught:
            replay_ego.jygs_replay_ego(timeout=1)
        assert 'secret' not in str(caught.value)


def test_invalid_date():
    with pytest.raises(ValueError):
        replay_ego.jygs_replay_ego('invalid', timeout=1)


def test_single_login_response(monkeypatch):
    record = {'endpoint': replay._API + 'count-pc', 'body': json.dumps({'errCode': 1})}
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        stdout='', stderr='FINCHX_RESULT=' + json.dumps([record])))
    with pytest.raises(SourceError, match='Ego 登录失效'):
        replay_ego.jygs_replay_ego(timeout=2)


def test_script_closes_page_on_failure_and_stops_on_user_control():
    import shutil

    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    # Execute the actual script with a minimal public API stub, including its catch path.
    stub = '''
const page = {
  cdp: async () => { throw new Error(FAILURE); },
  close: async () => console.log('PAGE_CLOSED')
};
const taskSpace = async () => ({page: () => page});
'''
    payload = json.dumps({'url': 'https://example.org', 'api': replay._API,
                          'timeout': 2, 'name': 'test'})
    for failure, should_close in [('network failure', True), ('EGO_TASK_SPACE_INACTIVE', False)]:
        script = stub.replace('FAILURE', json.dumps(failure)) + '\ntry {\n' + replay_ego._SCRIPT.replace('INPUT', payload, 1) + '\n} catch {}\n'
        output = _run_node_script(node, script)
        assert ('PAGE_CLOSED' in output) is should_close


def test_script_returns_single_login_response():
    import shutil

    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    stub = '''
let calls = 0;
const page = {
  cdp: async (method) => method === 'Network.getResponseBody' ? {body: '{"errCode":1}', base64Encoded: false} : {},
  goto: async () => {}, waitForFunction: async () => {}, click: async () => {},
  events: async () => ++calls === 1 ? [] : [
    {method:'Network.requestWillBeSent', params:{requestId:'1', request:{url: API + 'count-pc', method:'POST', postData:'{"date":"2026-10-30"}'}}},
    {method:'Network.responseReceived', params:{requestId:'1', response:{status:200}}},
    {method:'Network.loadingFinished', params:{requestId:'1'}}
  ],
  close: async () => {}
};
const taskSpace = async () => ({page: () => page, finish: async () => {}});
'''.replace('API', json.dumps(replay._API))
    payload = json.dumps({'url': 'https://example.org', 'api': replay._API,
                          'timeout': 2, 'name': 'test'})
    script = stub + '\n{\n' + replay_ego._SCRIPT.replace('INPUT', payload, 1) + '\n}\n'
    output = _run_node_script(node, script)
    records = json.loads(output.split('FINCHX_RESULT=', 1)[1])
    assert len(records) == 1
    assert json.loads(records[0]['body']) == {'errCode': 1}
