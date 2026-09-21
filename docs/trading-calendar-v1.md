# Trading Calendar v1

## Contract

- Dataset identity: trading_calendar@1.0
- Canonical scope: Market.CN_A, shared by SSE, SZSE, and BSE equity trading dates.
- Request: TradingCalendarRequest(market, start_date, end_date).
- The only supported market is Market.CN_A; callers do not select an exchange or data source.
- Bounds are inclusive. A request from 2026-09-01 through 2026-09-30 returns 30 records.
- Payload: date and isTradingDay, with one record for every natural date.
- Records are sorted ascending; duplicate, missing, out-of-range, or non-contiguous dates fail validation.
- StandardRecord.entityId and recordId are the stable opaque key CN_A:YYYY-MM-DD. Calendar rows do not use InstrumentId.
- The payload schema is finchx.schemas/v1/trading-calendar.schema.json.

Example:

    service = TradingCalendarService()
    records = service.get_calendar(
        TradingCalendarRequest(
            market=Market.CN_A,
            startDate=date(2026, 9, 1),
            endDate=date(2026, 9, 30),
        )
    )

Calling get_calendar is explicit network/data collection. Importing FinchX does not fetch data.

## Primary: SZSE official monthly calendar

Provider: SzseTradingCalendarProvider; source id: szse.official.calendar.

The online source for the shared canonical CN_A calendar is the SZSE official monthly calendar. This does not imply that SZSE's calendar is the SSE or BSE official calendar.

- Endpoint: https://www.szse.cn/api/report/exchange/onepersistenthour/monthList
- Method: GET
- Query: month=YYYY-MM, one request for each calendar month intersecting the requested range.
- Headers used in the successful live request: browser User-Agent, Accept: application/json, text/javascript, */*;q=0.8, and Referer: https://www.szse.cn/aboutus/calendar/.
- No account, cookie, API key, or proxy is required.
- Response envelope: an object with data, a list of daily objects.
- jyrq is an ISO calendar date. jybz="1" means trading day; jybz="0" means closed. Other flag values fail. zrxh is ignored.
- Each response must contain exactly every natural date in its requested month. Month lengths use Python's standard calendar.monthrange.
- Dates outside the requested month, duplicates, invalid flags, missing dates, and invalid envelopes are provider failures. Weekdays are never inferred or used to fill a missing official row.
- A multi-month request fetches all intersecting months, validates each entire month, then slices the inclusive user range. Any month failure discards all Primary rows for that request.

capturedAt is recorded immediately after each HTTP response is received. All rows from one response share that timestamp; rows from different month responses can have different timestamps. eventAt and asOf remain null because calendar dates are labels, not event instants.

## Fallback: pandas_market_calendars

Provider: PmcTradingCalendarProvider; source id: pandas_market_calendars.

The runtime dependency constraint is pandas_market_calendars>=5.4,<6. The implementation was inspected and tested with the latest PyPI release, version 5.4.0 ([PyPI release page](https://pypi.org/project/pandas_market_calendars/)). Its actual supported calendar names included SSE and XSHG; FinchX selects SSE, which resolves to SSEExchangeCalendar in that version. FinchX reads only the schedule index's session dates and does not expose open/close times, session hours, lunch breaks, or exchange timezones in the payload.

The adapter constructs the inclusive list of natural dates, obtains one SSE schedule for the whole request, and marks membership in that schedule as isTradingDay=true; every other date is false. It uses session date labels directly, not host locale or system timezone conversion.

If any Primary month or canonical range validation fails, the whole request is retried through PMC. It never combines months from different providers. Every fallback record identifies pandas_market_calendars as its source. Fallback calendar rows remain DataStatus.LIVE; fallback is a source choice, not a new status or an estimate.

PMC is an offline fallback, not official truth. Its holiday definitions depend on the installed package version. Version 5.3.0 added Chinese holiday data for 2026 and 2027 ([upstream changelog](https://github.com/rsheftel/pandas_market_calendars/blob/master/docs/change_log.rst)). Version 4.6.1 initially marked 2026-02-23, 2026-05-04, and 2026-05-05 as sessions while SZSE marked them closed. PMC 5.3.0 added China holiday data for 2026 and 2027; after upgrading to 5.4.0, all six tested months match the official SZSE response. FinchX still treats PMC as an offline fallback rather than official truth, because its holiday tables ship with the package and can become stale.

## Live comparison (captured 2026-09-17)

Comparison uses direct SZSE responses and the isolated latest PMC 5.4.0 SSE install. “Mismatch” counts dates where the boolean trading flag differs. The previous local version 4.6.1 had three mismatches in February and May 2026; 5.4.0 had none.

| Month | Natural dates | SZSE trading days | PMC trading days | Compared dates | Mismatches |
|---|---:|---:|---:|---:|---|
| 2026-02 | 28 | 14 | 14 | 28 | 0 |
| 2026-05 | 31 | 18 | 18 | 31 | 0 |
| 2026-09 | 30 | 21 | 21 | 30 | 0 |
| 2026-10 | 31 | 17 | 17 | 31 | 0 |
| 2025-10 | 31 | 17 | 17 | 31 | 0 |
| 2024-02 | 29 | 15 | 15 | 29 | 0 |
| **Total** | **180** | — | — | **180** | **0** |

The official 2026-10 month had been published by SZSE at capture time. The comparison is a finite sample, not a guarantee for future or untested years. SZSE remains the online authority selected for FinchX's shared CN_A calendar.

## Record source and time semantics

- Primary source id: szse.official.calendar.
- Fallback source id: pandas_market_calendars.
- Both return ordinary standardized calendar facts with DataStatus.LIVE; source.providerId distinguishes the source.
- Primary capturedAt is per official month response. PMC rows share one capture time for the local schedule calculation.
- eventAt, publishedAt, updatedAt, and asOf are null. The business date is only data.date.
- Provenance.recordClass is standardized; transformation version is trading-calendar-normalizer/1.

## Scope and limitations

- SSE, SZSE, and BSE equity trading dates are treated as one CN_A calendar in FinchX v1.
- This dataset answers only whether each date is a trading day. It does not return session hours or previous/next trading-day helpers.
- No calendar cache is implemented.
- PMC holiday accuracy is version-dependent. Version 4.6.1 differed from SZSE on three tested 2026 dates; version 5.4.0 matched all six sample months. Use PMC only when the official request cannot complete.
- Normative schemas are packaged under `finchx.schemas/v1/` and loaded through the package resource loader.
- FinchX has no dependency on any downstream application.
