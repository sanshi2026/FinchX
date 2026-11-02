"""使用 Ego 浏览器采集官网复盘。"""

import json
import subprocess
import uuid

from finchx._common.convert import parse_date_parameter, validate_timeout
from finchx._common.errors import SourceError
from finchx.sources.jiuyangongshe import replay

_SCRIPT = r'''
const input = INPUT;
const deadline = Date.now() + input.timeout * 1000;
const remaining = () => { const n = deadline - Date.now(); if (n <= 0) throw new Error('timeout'); return n; };
const task = await taskSpace(input.name);
const page = task.page('p1');
try {
await page.cdp('Network.enable', {}, {timeout: remaining()});
await page.goto(input.url, {timeout: remaining()});
await page.waitForFunction(() => Boolean(window.$nuxt && window.$nuxt._isMounted), undefined, {timeout: remaining()});
await page.events();
await page.click('text="全部异动解析" >> nth=0', {timeout: remaining()});
const records = [];
while (remaining() > 0) {
  for (const event of await page.events()) {
    const p = event.params;
    if (event.method === 'Network.requestWillBeSent') {
      const url = p.request.url.split('?')[0];
      if (p.request.method === 'POST' && (url === input.api + 'count-pc' || url === input.api + 'field')) {
        records.push({id:p.requestId, endpoint:url, method:p.request.method, post:p.request.postData});
      }
    } else if (event.method === 'Network.responseReceived') {
      const r = records.find(x => x.id === p.requestId);
      if (r) r.status = p.response.status;
    } else if (event.method === 'Network.loadingFailed') {
      const r = records.find(x => x.id === p.requestId);
      if (r) throw new Error('request failed');
    } else if (event.method === 'Network.loadingFinished') {
      const r = records.find(x => x.id === p.requestId);
      if (r) { const body = await page.cdp('Network.getResponseBody', {requestId:r.id}, {timeout: remaining()}); r.body = body.base64Encoded ? Buffer.from(body.body, 'base64').toString('utf8') : body.body; }
    }
  }
  const count = records.find(x => x.endpoint === input.api + 'count-pc' && x.body !== undefined);
  if (count && JSON.parse(count.body).errCode != 0) break;
  if (records.length >= 2 && records.every(x => x.body !== undefined)) break;
  await page.waitForTimeout(Math.min(100, remaining()));
}
for (const r of records) { const p = JSON.parse(r.post); r.post = JSON.stringify({date:p.date, pc:p.pc}); }
console.log('FINCHX_RESULT=' + JSON.stringify(records));
await task.finish({keep:[]});
} catch (error) {
  // 用户接管时停止操作；其他错误只关闭本任务创建的页面。
  if (!/control|inactive|unassigned|delegated|EGO_TASK_SPACE/i.test(String(error))) {
    try { await page.close(); } catch {}
  }
  throw error;
}
'''


def _capture(url: str, timeout: float):
    payload = {"url": url, "api": replay._API, "timeout": timeout,
               "name": "FinchX replay " + uuid.uuid4().hex}
    script = _SCRIPT.replace("INPUT", json.dumps(payload, ensure_ascii=True), 1)
    try:
        result = subprocess.run(["ego-browser", "nodejs"], input=script, text=True, encoding="utf-8",
                                capture_output=True, timeout=timeout + 2, check=True)
        line = next(line for line in (result.stdout + "\n" + result.stderr).splitlines() if line.startswith("FINCHX_RESULT="))
        records = json.loads(line.partition("=")[2])
        if records and records[0].get("endpoint") == replay._API + "count-pc" and "body" in records[0]:
            count_document = json.loads(records[0]["body"])
            if isinstance(count_document, dict) and type(count_document.get("errCode")) in (int, str) and count_document.get("errCode") in (1, "1"):
                raise SourceError(replay.SOURCE, "Ego 登录失效，请在 Ego Lite 登录韭研公社")
            replay._response_data(count_document, "count-pc")
        if len(records) != 2:
            raise ValueError
        count, field = records
        if [count["endpoint"], field["endpoint"]] != [replay._API + "count-pc", replay._API + "field"]:
            raise ValueError
        values = []
        for record in records:
            post = json.loads(record["post"])
            if record["method"] != "POST" or not 200 <= record["status"] < 300 or not isinstance(post, dict):
                raise ValueError
            values.append((json.loads(record["body"]), replay._source_date(post.get("date"), "官网请求.date")))
        if isinstance(json.loads(field["post"]).get("pc"), bool) or json.loads(field["post"]).get("pc") != 1:
            raise ValueError
        return values[0][0], values[1][0], values[0][1], values[1][1]
    except FileNotFoundError:
        raise SourceError(replay.SOURCE, "未找到 ego-browser，请先安装并启动 Ego Lite") from None
    except subprocess.TimeoutExpired:
        raise SourceError(replay.SOURCE, "Ego 官网复盘采集超时") from None
    except (subprocess.CalledProcessError, StopIteration, ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise SourceError(replay.SOURCE, "Ego 官网复盘采集失败，请检查浏览器登录状态和连接") from None


def jygs_replay_ego(date: str | None = None, *, timeout: float) -> dict:
    if date is not None:
        date = parse_date_parameter(date, "date").isoformat()
    seconds = validate_timeout(timeout)
    url = replay._ORIGIN + "/action" + (f"/{date}" if date is not None else "")
    count, field, count_date, field_date = _capture(url, seconds)
    if isinstance(count, dict) and type(count.get("errCode")) in (int, str) and count.get("errCode") in (1, "1"):
        raise SourceError(replay.SOURCE, "Ego 登录失效，请在 Ego Lite 登录韭研公社")
    if isinstance(field, dict) and type(field.get("errCode")) in (int, str) and field.get("errCode") in (1, "1"):
        raise SourceError(replay.SOURCE, "Ego 登录失效，请在 Ego Lite 登录韭研公社")
    data = replay._response_data(count, "count-pc")
    if not isinstance(data, dict):
        raise SourceError(replay.SOURCE, "count-pc data 结构损坏")
    actual = replay._source_date(data.get("date"), "count-pc.date")
    if field_date != actual or actual > count_date or (date is not None and count_date > date):
        raise SourceError(replay.SOURCE, "官网 count-pc 与 field 请求日期未关联同一次复盘")
    return replay._parse_replay(count, field, date)
