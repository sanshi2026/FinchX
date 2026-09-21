# 交易日历

[English](TRADING_CALENDAR.md) | 简体中文

`trading_calendar@1.0` 为闭区间范围内的每个自然日返回一行记录。每行包含 `date` 和 `isTradingDay`。结果按日期升序排列、完整且不重复，并在 SSE、SZSE 和 BSE 股票场景中使用共享的 `Market.CN_A` 范围。

交易日历只回答某个日期是否为交易日，不返回交易时段、午休、开盘/收盘时间戳或前一交易日/后一交易日辅助方法。

## 请求

```python
from datetime import date
from finchx import FinchX
from finchx.entities import Market

result = FinchX().reference.trading_calendar(
    date(2026, 9, 1), date(2026, 9, 30), market=Market.CN_A
)
for record in result.data:
    print(record.data["date"], record.data["isTradingDay"])
```

起止边界均包含在内。唯一支持的市场是 `Market.CN_A`；调用方不选择交易所。

## Provider

主要在线来源是 `szse.official.calendar`。它会从深交所官方月度日历请求与范围相交的每个自然月。响应必须明确包含请求月份中的每一个自然日；FinchX 不会根据工作日规则补齐缺失行。

`pandas_market_calendars` 是可选的离线 fallback Provider。使用 `calendar` extra 安装它。fallback 会将包内的交易所日程展开到所有自然日，并标记交易时段成员关系。其节假日表取决于包版本，因此 Provider id 会保留在 provenance 中。

如果任何主要来源月份在传输、解析或完整性校验阶段失败，运行时会根据配置的 fallback 策略处理完整的请求范围；它不会在同一个结果中混合主要来源和 fallback 的行。

## 记录语义

稳定的记录身份是 `CN_A:YYYY-MM-DD`。日历日期是标签而不是时刻，因此 `eventAt` 和 `asOf` 为 null。`capturedAt` 记录获取来源响应的时间，`source.providerId` 标识主要来源或 fallback Provider。

规范 schema 以 `finchx.schemas/v1/trading-calendar.schema.json` 的形式打包，并通过 package resource API 加载。
