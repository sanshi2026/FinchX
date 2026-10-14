"""研报原生关键词检索、日期筛选和有限候选聚合。"""

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from threading import Event, Lock
from time import monotonic

from finchx._common.convert import parse_date_parameter, validate_timeout
from finchx._common.errors import FinchXError, SourceError
from finchx.sources.aigupiao import reports_fetch as aigupiao
from finchx.sources.eastmoney import reports as eastmoney
from finchx.sources.analysys import reports as analysys

_FIELDS = ("source", "title", "institute", "publication_date", "url", "content", "content_type", "pdf_urls")


@dataclass
class _State:
    source: str
    rows: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    valid: bool = False
    cursor: int | None = None
    started: bool = False
    unavailable: bool = False
    cursor_error: bool = False
    seen: set = field(default_factory=set)
    stagnant: int = 0
    details: dict = field(default_factory=dict)
    aliases: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)


def _remaining(deadline: float, source: str, stop: Event | None = None) -> float:
    if stop is not None and stop.is_set():
        raise SourceError(source, "研报请求已结束，来源未完成")
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise SourceError(source, "研报检索时间预算已用完，来源未完成")
    return seconds


def _error(state: _State, url: str | None, reason: str) -> None:
    with state.lock:
        item = {"source": state.source, "url": url, "reason": reason}
        if item not in state.errors:
            state.errors.append(item)


def _prepare(module, state: _State, keyword: str, limit: int, start, end, deadline: float, stop: Event) -> None:
    cursor = state.cursor if state.started else (0 if state.source == "aigupiao" else 1)
    seen, details, aliases = state.seen, state.details, state.aliases
    try:
        if state.cursor_error:
            raise SourceError(state.source, "研报分页持续停滞，来源未完成")
        while cursor is not None:

            rows, next_cursor = module.search_page(keyword, cursor, timeout=_remaining(deadline, state.source, stop))
            with state.lock:
                state.valid = True
            new = False
            for original in rows:
                row = dict(original)
                native_id = row.get("_id") or row["url"]
                identity = aliases.get(("id", native_id), aliases.get(("url", row["url"]), native_id))
                aliases[("id", native_id)] = identity
                aliases[("url", row["url"])] = identity
                if identity not in seen:
                    new = True
                seen.add(identity)
                if identity not in state.positions:
                    state.positions[identity] = len(state.positions)
                # 缺年份的发布日期仅能由正式详情确认；rec_time 不是发布日期。
                if identity in details:
                    row = {**row, **details[identity]}
                if row.get("publication_date") is None and not row.get("_detail_read") and not row.get("_detail_failed") and (start or end or row.get("_date_text")):
                    before_detail = dict(row)
                    try:
                        row = module.get_detail(row, timeout=_remaining(deadline, state.source, stop))
                        row["_detail_read"] = True
                    except SourceError as exc:
                        _error(state, row["url"], exc.reason)
                        row["_detail_failed"] = True
                    fields = {"content", "content_type", "pdf_urls", "_detail_read", "_detail_failed"}
                    fields.update(row.get("_detail_fields", ()))
                    fields.update(key for key in ("title", "institute", "publication_date")
                                  if row.get(key) != before_detail.get(key))
                    details[identity] = {key: row[key] for key in fields if key in row}
                day = row.get("publication_date")
                eligible = not ((start and (day is None or day < start)) or (end and (day is None or day > end)))
                with state.lock:
                    if eligible:
                        state.rows[identity] = row
                    else:
                        state.rows.pop(identity, None)
            state.stagnant = 0 if new else state.stagnant + 1
            state.cursor_error = next_cursor is not None and (
                (next_cursor >= cursor if state.source == "aigupiao" and cursor else next_cursor <= cursor)
                or state.stagnant >= 3)
            with state.lock:
                state.cursor, state.started = next_cursor, True
                enough = len(state.rows) >= limit
            if enough or next_cursor is None:
                return
            if state.cursor_error:
                raise SourceError(state.source, "研报分页持续停滞，来源未完成")
            cursor = next_cursor
    except SourceError as exc:
        state.unavailable = True
        _error(state, None, exc.reason)


def _detail(module, row: dict, deadline: float, stop: Event) -> dict:
    return module.get_detail(row, timeout=_remaining(deadline, row["source"], stop))


def fetch(keyword: str, limit: int = 20, start_date: str | None = None,
          end_date: str | None = None, *, timeout: float) -> dict:
    """仅在各来源日期合格候选中排序，返回选定报告及明确的来源错误。"""
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("keyword 必须是非空字符串")
    try:
        keyword.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("keyword 必须是有效 Unicode 字符串") from exc
    if any(ord(char) < 32 or ord(char) == 127 for char in keyword):
        raise ValueError("keyword 不能含控制字符")
    if type(limit) is not int or limit <= 0:
        raise ValueError("limit 必须是正整数")
    start = parse_date_parameter(start_date, "start_date").isoformat() if start_date is not None else None
    end = parse_date_parameter(end_date, "end_date").isoformat() if end_date is not None else None
    if start and end and start > end:
        raise ValueError("start_date 不能晚于 end_date")
    deadline = monotonic() + validate_timeout(timeout)
    modules = (("aigupiao", aigupiao), ("eastmoney", eastmoney), ("analysys", analysys))
    states = [_State(source) for source, _ in modules]
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="finchx-reports")
    search_stop, detail_stop = Event(), Event()
    try:
        jobs = {executor.submit(_prepare, module, state, keyword, limit, start, end, deadline, search_stop): state
                for (_, module), state in zip(modules, states)}
        done, pending = wait(jobs, timeout=max(0, deadline - monotonic()))
        for job in done:
            job.result()  # 编程错误不能伪装为正常空结果。
        search_stop.set()
        for job in pending:
            job.cancel()
            jobs[job].unavailable = True
            _error(jobs[job], None, "研报检索时间预算已用完，来源未完成")
        candidates, errors, valid = [], [], False
        for rank, state in enumerate(states):
            with state.lock:
                valid |= state.valid
                errors.extend(state.errors)
                candidates.extend((rank, state.positions[identity], dict(row)) for identity, row in state.rows.items())
        if not valid:
            raise FinchXError("所有研报来源均请求失败", errors=tuple(SourceError(item["source"], item["reason"]) for item in errors))
        def order(item):
            day = item[2].get("publication_date")
            return (day is None, -int(day.replace("-", "")) if day else 0, item[0], item[1])

        def eligible(row):
            day = row.get("publication_date")
            return not ((start and (day is None or day < start)) or (end and (day is None or day > end)))

        def report_key(item):
            row = item[2]
            title, institute = row.get("title"), row.get("institute")
            if title and institute:
                return ("report", title, institute)
            # 缺标题或机构时，只有来源内部身份可确认，不合并缺失值。
            return ("identity", item[0], item[1])

        def representative_order(item):
            row = item[2]
            coverage = bool(row.get("content")) + bool(row.get("pdf_urls"))
            confirmed = row.get("_detail_read") or row.get("pdf_urls") is not None
            return (*order(item)[:2], bool(row.get("_detail_failed")), not confirmed,
                    -coverage, item[0], item[1])

        def unique_candidates(records):
            representatives = {}
            for item in records:
                key = report_key(item)
                previous = representatives.get(key)
                if previous is None or representative_order(item) < representative_order(previous):
                    representatives[key] = item
            return sorted(representatives.values(), key=order)

        # 搜索和详情各有一份客户端预算；慢搜索不挤占成功来源的正文读取。
        detail_deadline = monotonic() + validate_timeout(timeout)
        lookup = dict(modules)
        def snapshot():
            records = []
            for rank, state in enumerate(states):
                with state.lock:
                    records.extend((rank, state.positions[identity], dict(row)) for identity, row in state.rows.items())
                    for error in state.errors:
                        if error not in errors:
                            errors.append(error)
            return records

        def remember(item, before):
            state, row = states[item[0]], item[2]
            identity = state.aliases.get(("id", row.get("_id")), state.aliases.get(("url", row["url"])))
            if identity is None:
                return
            fields = {"content", "content_type", "pdf_urls", "_detail_read", "_detail_failed"}
            fields.update(row.get("_detail_fields", ()))
            fields.update(key for key in ("title", "institute", "publication_date") if row.get(key) != before.get(key))
            with state.lock:
                state.details[identity] = {key: row[key] for key in fields if key in row}
                if eligible(row):
                    state.rows[identity] = dict(row)
                else:
                    state.rows.pop(identity, None)

        while True:
            candidates = [item for item in candidates if eligible(item[2])]
            chosen = unique_candidates(candidates)[:limit]
            if len(chosen) < limit:
                missing = limit - len(chosen)
                resumable = [state for state in states if state.started and state.cursor is not None and not state.unavailable]
                if resumable:
                    jobs = {executor.submit(_prepare, lookup[state.source], state, keyword,
                                            len(state.rows) + missing, start, end, detail_deadline, detail_stop): state
                            for state in resumable}
                    done, pending = wait(jobs, timeout=max(0, detail_deadline - monotonic()))
                    for job in done:
                        job.result()
                    for job in pending:
                        job.cancel()
                        jobs[job].unavailable = True
                        _error(jobs[job], None, "研报补取时间预算已用完，来源未完成")
                    if pending:
                        detail_stop.set()
                    candidates = snapshot()
                    continue
            # 同组副本也读详情：正式元信息可改变分组，失败副本不能遮住可读报告。
            chosen_keys = {report_key(item) for item in chosen}
            details = {executor.submit(_detail, lookup[item[2]["source"]], dict(item[2]), detail_deadline, detail_stop): item
                       for item in candidates if report_key(item) in chosen_keys
                       if not item[2].get("_detail_read") and not item[2].get("_detail_failed") and item[2].get("pdf_urls") is None}
            if not details:
                break
            done, pending = wait(details, timeout=max(0, detail_deadline - monotonic()))
            for job in done:
                item = details[job]
                row = item[2]
                before = dict(row)
                try:
                    updated = job.result()
                    updated["_detail_read"] = True
                    row.clear()
                    row.update(updated)
                except SourceError as exc:
                    row["_detail_failed"] = True
                    errors.append({"source": row["source"], "url": row["url"], "reason": exc.reason})
                remember(item, before)
            for job in pending:
                job.cancel()
                row = details[job][2]
                before = dict(row)
                row["_detail_failed"] = True
                remember(details[job], before)
                errors.append({"source": row["source"], "url": row["url"], "reason": "研报详情时间预算已用完"})
            if pending:
                detail_stop.set()
            # 详情修正标题、机构或日期后重新分组排序，必要时继续补页。
        selected = [item[2] for item in chosen]
        return {"reports": [{key: row.get(key) for key in _FIELDS} for row in selected], "errors": errors}
    finally:
        # urllib 请求使用剩余预算；关闭调度不额外等待超时任务，也不启动后台新请求。
        search_stop.set()
        detail_stop.set()
        executor.shutdown(wait=False, cancel_futures=True)
