# FinchX

[English](https://github.com/sanshi2026/FinchX/blob/main/README.md) | 简体中文

[PyPI](https://pypi.org/project/finchx/) · [源代码](https://github.com/sanshi2026/FinchX) · [发行说明](https://github.com/sanshi2026/FinchX/blob/main/CHANGELOG.md) · [许可证](https://github.com/sanshi2026/FinchX/blob/main/LICENSE)

FinchX 是一个独立的 Python 库，用于访问和标准化已注册第三方数据源提供的 A 股市场数据。类型化客户端按行情、财务与公司数据、新闻、文档和市场热榜等常见场景组织接口。

## 安装

```bash
python -m pip install finchx
```

要求 Python 3.10 或更高版本；基础安装会自动安装 FinchX 所需的运行时依赖。

可选集成：

- `calendar` 为 `pandas_market_calendars` 交易日历 Provider 安装依赖：`python -m pip install "finchx[calendar]"`。
- `jygs` 启用需要认证的韭研公社每日复盘 Provider：`python -m pip install "finchx[jygs]"`。此外还需安装 Chromium：`python -m playwright install chromium`。

## 快速开始

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote_snapshot(
    instrument="600519",  # 六位 A 股代码。
)

# result.data 包含 StandardRecord；每条记录的 record.data 是业务数据。
if result.data:
    record = result.data[0]
    print(record.data["price"])

# to_dicts() 将业务数据导出为字典列表。
rows = result.to_dicts()
print(rows[:1])
print(result.warnings)
```

获取日线历史时，`fx.market.ohlcv(...)` 的开始和结束日期均包含在查询范围内：

```python
from finchx import FinchX

fx = FinchX()
bars = fx.market.ohlcv(
    instrument="600519",  # 六位 A 股代码。
    start_date="2026-09-01",  # 包含在内的开始日期。
    end_date="2026-09-23",  # 包含在内的结束日期。
    adjustment="qfq",  # 股票前复权。
)
print(bars.to_dicts()[:1])
```

股票前复权使用 `adjustment="qfq"`，后复权使用 `"hfq"`，不复权使用 `None`；指数 OHLCV 必须传入 `None`。

## 按场景查找接口

- **行情与历史数据：** `fx.market.quote(...)`、`fx.market.quote_snapshot(...)`、`fx.market.ohlcv(...)`、`fx.market.deviation(...)`。
- **参考与公司数据：** `fx.reference.trading_calendar(...)`、`fx.fundamental.financial_summary(...)`、`fx.financial.statements(...)`，以及 `fx.ownership`、`fx.company`、`fx.corporate_action`。
- **新闻与文档：** `fx.news.search(...)`、`fx.disclosure.search(...)`、`fx.market_news.search(...)` 和 `fx.articles.get(...)`。
- **热榜与发现：** `fx.hotlist.stocks(...)`、`fx.hotlist.sectors(...)` 和 `fx.iwencai.select(...)`。

以上是常用入口，并非完整接口清单。完整签名、数据字段、返回结构和 Provider 信息请见 API 参考。

## 输入和数据来源

单标的接口接受六位代码；接口会判断类似 `000001` 的代码表示股票还是指数。仅日期参数接受 `datetime.date`，或 `YYYY-MM-DD`、`YYYYMMDD`、`YYYY/MM/DD` 格式的字符串；`09/01/2026` 等歧义格式会被拒绝。新闻、公告、全市场新闻和论坛时间范围也接受带时区的 `datetime`。

部分数据源功能需要调用者提供凭据，例如 `fx.iwencai.select(...)` 需要登录 Cookie，`fx.iwencai.search(...)` 需要 API Key，`fx.forum.replies(...)` 和 `fx.market.daily_replay(...)` 需要会话 Cookie。请勿将凭据提交到源码仓库。

FinchX 会标准化第三方数据源的响应，但不重新分发其数据集。数据是否可用、包含哪些字段、更新频率及使用条款由各数据源决定。

## 完整 API 参考

- [English API reference](https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.md)
- [简体中文 API 参考](https://github.com/sanshi2026/FinchX/blob/main/docs/DATA_API_REFERENCE.zh-CN.md)

FinchX 使用 Apache-2.0 许可证；第三方数据仍受相应数据源条款约束。
