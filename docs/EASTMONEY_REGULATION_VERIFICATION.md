# EastMoney regulation live verification

This is a record of the low-frequency live probes performed during implementation on 2026-09-27. The initial six capability probes were run through FinchX's Provider adapter; their per-request timestamps and numeric HTTP status codes were not retained in the phase handoff. The four follow-up diagnostics below were run directly against EastMoney's public JSON endpoints with per-request UTC timestamps and exact query parameters. These counts are point-in-time observations and are not fixtures or ongoing availability guarantees.

| Public capability / request | Endpoint business status | Rows returned | Pagination observation |
| --- | --- | ---: | --- |
| `market.regulation_watchlist()` | Top-level JSON array parsed and normalized | 17 | Unpaged; complete response |
| `market.abnormal_records(dataset="abnormal_events", page_size=2)` | DataCenter `success=true`, `code=0` | 2 | `pages=2742`; more pages available |
| `market.abnormal_records(dataset="severe_events", status="current")` | DataCenter `success=true`, `code=0` | 1 | One source page; complete |
| `market.abnormal_records(dataset="prediction_history", page_size=2)` | DataCenter `success=true`, `code=0` | 2 | `pages=2031`; more pages available |
| `market.severe_predictions()` | `/price-anomaly/list` `result=0` | 16 | One source page; complete |
| `market.abnormal_counts()` | `/price-anomaly/count` `result=0` | 15 | One source page; complete |

All six responses normalized to FinchX `StandardRecord` rows without warnings. Pool pagination was determined from the source `pages` fields. The DataCenter checks validated both the HTTP response and the business envelope; the pool checks validated `result=0`, data arrays, and required row fields. A successful transport response alone was not treated as a successful probe.

The live calls can be repeated from the repository root with:

```python
from finchx import FinchX

fx = FinchX()
results = {
    "watchlist": fx.market.regulation_watchlist(),
    "abnormal_events": fx.market.abnormal_records(dataset="abnormal_events", page_size=2),
    "severe_current": fx.market.abnormal_records(dataset="severe_events", status="current"),
    "prediction_history": fx.market.abnormal_records(dataset="prediction_history", page_size=2),
    "severe_predictions": fx.market.severe_predictions(),
    "abnormal_counts": fx.market.abnormal_counts(),
}
for name, result in results.items():
    print(name, len(result.data), dict(result.metadata), result.warnings)
```

The live endpoints can change their row counts and page totals at any time. The finite page cap on the two pool methods and the one-page contract on `abnormal_records` remain in force during reproduction.

## Exact low-frequency diagnostics for report and horizon semantics

The following four GET requests were made sequentially on 2026-09-27 from 11:21:10.094 to 11:21:11.096 UTC. Only response summaries were saved; no security rows or names were persisted.

| Probe | Started / completed (UTC) | HTTP status | Endpoint business status | Rows / pages / source flags |
| --- | --- | ---: | --- | --- |
| DataCenter, one unfiltered report | 11:21:10.094 / 11:21:10.287 | 200 | `success=true`, `code=0`, `message=ok` | 20 rows; `count=5662`, `pages=284`; first page had 20 `UNUSUAL_TYPE=001` rows |
| DataCenter, comma-joined report names | 11:21:10.287 / 11:21:10.538 | 200 | `success=false`, `code=9501`, `message=报表配置不存在,RPT_APP_UNUSUALBASIC,RPT_WATCH_UNUSUAL_FLUCTUATE` | No result rows |
| DataCenter, same report with tested `or` filter expression | 11:21:10.538 / 11:21:10.875 | 200 | `success=false`, `code=9501`, `message=参数预处理错误:org.antlr.v4.runtime.InputMismatchException` | No result rows; this one expression was rejected and does not establish whether another OR syntax is supported |
| Prediction list, one page, no horizon argument | 11:21:10.875 / 11:21:11.096 | 200 | `result=0`, empty `msg` | 16 rows; `pages=1`; `o=0`: 8, `o=2`: 8 |

Exact request URLs (with no credentials or user-specific values):

```text
https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_APP_UNUSUALBASIC&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CUNUSUAL_TYPE%2CSTART_DATE%2CEND_DATE%2CINFO_CODE%2CNOTICE_DATE%2CUNUSUAL_REASON%2CUNUSUAL_REASON_TYPE%2CMRAKET_TYPE%2CPREDICT_START_DATE%2CPREDICT_END_DATE%2CIS_HIS&quoteColumns=&filter=&pageNumber=1&pageSize=20&sortColumns=NOTICE_DATE%2CEND_DATE&sortTypes=-1%2C-1&source=SECURITIES&client=APP
https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_APP_UNUSUALBASIC%2CRPT_WATCH_UNUSUAL_FLUCTUATE&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CUNUSUAL_TYPE%2CSTART_DATE%2CEND_DATE%2CINFO_CODE%2CNOTICE_DATE%2CUNUSUAL_REASON%2CUNUSUAL_REASON_TYPE%2CMRAKET_TYPE%2CPREDICT_START_DATE%2CPREDICT_END_DATE%2CIS_HIS&quoteColumns=&filter=&pageNumber=1&pageSize=20&sortColumns=NOTICE_DATE%2CEND_DATE&sortTypes=-1%2C-1&source=SECURITIES&client=APP
https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_APP_UNUSUALBASIC&columns=SECUCODE%2CSECURITY_CODE%2CSECURITY_NAME_ABBR%2CUNUSUAL_TYPE%2CSTART_DATE%2CEND_DATE%2CINFO_CODE%2CNOTICE_DATE%2CUNUSUAL_REASON%2CUNUSUAL_REASON_TYPE%2CMRAKET_TYPE%2CPREDICT_START_DATE%2CPREDICT_END_DATE%2CIS_HIS&quoteColumns=&filter=%28UNUSUAL_TYPE%3D%22001%22+or+UNUSUAL_TYPE%3D%22002%22%29&pageNumber=1&pageSize=20&sortColumns=NOTICE_DATE%2CEND_DATE&sortTypes=-1%2C-1&source=SECURITIES&client=APP
https://dycalchis.eastmoney.com/price-anomaly/list?team=h5&product=EastMoney&client=WAP&version=9001&name=WAP&user=123&pageSize=200&pageNo=1&riseOnly=0&showBJS=1
```

The first three requests used columns `SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,UNUSUAL_TYPE,START_DATE,END_DATE,INFO_CODE,NOTICE_DATE,UNUSUAL_REASON,UNUSUAL_REASON_TYPE,MRAKET_TYPE,PREDICT_START_DATE,PREDICT_END_DATE,IS_HIS`, `quoteColumns=`, `pageNumber=1`, `pageSize=20`, `sortColumns=NOTICE_DATE,END_DATE`, `sortTypes=-1,-1`, `source=SECURITIES`, and `client=APP`. They differ only in `reportName` and, for the third, `filter` as shown in the exact URLs. The prediction-list call has no `horizon` parameter; its sampled response contains both `o=0` and `o=2`. This confirms those states can arrive together in a single response, while source state `o=1` and unknown states were not present in this live sample; unknown-state preservation is covered by local normalization tests.

The diagnostic results do not prove a successful multi-report or combined ordinary/severe filter request. HTTP 200 alone was insufficient for both rejected DataCenter probes; FinchX must check the endpoint's business envelope.
