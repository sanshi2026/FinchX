# 市场偏离值

[English](DEVIATION.md) | 简体中文

`market.deviation` 是 FinchX 针对一个明确标识的 A 股股票执行的确定性计算。它在指定的 10 或 30 个交易日窗口内，将股票的收盘价收益率与经过审计的板块基准进行比较。

它不是交易所公告、盘中估算、全市场扫描，也不是特定应用的触发状态。

## 范围

版本 1 支持 SSE `60xxxx`、`68xxxx` 股票，以及 SZSE `00xxxx`、`30xxxx` 股票。由于本版本尚未冻结相应的基准、规则集和价格来源，因此不支持 BSE。

输入必须是带有明确 SSE 或 SZSE 交易所的完整 `InstrumentId`。不支持的标的身份或不足的对齐历史数据会抛出现有的请求错误或无数据错误，不会产生零值。

## 基准

| 股票身份 | 板块 | 基准 |
| --- | --- | --- |
| SSE `60xxxx` | SSE 主板 | SSE A Share Index `000002` |
| SSE `68xxxx` | 科创板 | SSE STAR 50 Index `000688` |
| SZSE `00xxxx` | SZSE 主板 | SZSE A Share Index `399107` |
| SZSE `30xxxx` | 创业板 | ChiNext Composite Index `399102` |

映射使用完整标的身份，而不是单独的代码。解析出的基准会包含在每个返回的窗口中。

## 计算

对每个选定窗口：

```text
stock_return     = stock_end / stock_baseline - 1
benchmark_return = index_end / index_baseline - 1
deviation        = stock_return - benchmark_return
```

基准值是窗口起始日前一个交易日的收盘价或指数点。比率使用小数表示：`0.03` 表示 3%。

| 窗口 | 上阈值 | 下阈值 |
| ---: | ---: | ---: |
| 10 trading days | `+1.00` | `-0.50` |
| 30 trading days | `+2.00` | `-0.70` |

默认的 `max_deviation_scan` 约定会选择使股票与基准差值最大的合资格起点。`strict_exchange_window` 使用按交易所形状确定的起点。交易时段来自 `reference.trading_calendar`，不会使用简单的周末规则推算。

## 价格口径与来源

股票输入使用腾讯 QFQ 日 K 线收盘价，基准输入使用未复权指数序列。返回字段包括：

- `calculationMode = "official_close"`；
- `priceBasis = "qfq_stock__raw_index"`；以及
- `ruleVersion = "cn-a-exchange-2026-07-06+finchx-v1"`。

计算结果没有外部偏离值 Provider。其 `FetchResult` 的 provider 为 `None`；结果会保留计算所使用的交易日历和 K 线来源事实。

## API

```python
from finchx import FinchX
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market

instrument = InstrumentId(
    code="600519",
    market=Market.CN_A,
    kind=InstrumentKind.EQUITY,
    exchange=Exchange.SSE,
)
result = FinchX().market.deviation(instrument, windows=(10, 30))
for window in result.data.windows:
    print(window.window_days, window.deviation)
```

完整签名、返回字段、阈值和限制见 [API 参考](DATA_API_REFERENCE.zh-CN.md) 中的 `market.deviation` 章节。
