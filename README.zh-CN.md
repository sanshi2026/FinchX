# FinchX

[English](README.md) | 简体中文

FinchX 是一个独立的 Python 库，用于访问并标准化来自已注册第三方 Provider 的 A 股市场数据。

## FinchX 是什么？

主要入口是一个小型、带类型标注的客户端：

```python
from finchx import FinchX

fx = FinchX()
```

FinchX 提供九个 namespace、稳定的 `FetchResult` 外层结构、标准化的 Dataset 数据载荷、Provider 来源信息、受限的运行时路由，以及明确的计算型偏离值能力。

## 功能

- 行情、排名、K 线、盘中序列、盘口、资金流、涨跌停池和市场情绪。
- 标的身份信息和交易日历。
- 基本面、财务、股权、管理层和公司行为数据。
- 个股新闻和公告引用。
- 基于已实现东方财富契约、由数据源提供的股票关键词/概念。
- 面向支持的 A 股、基于收盘价的确定性个股与基准偏离值。

## 安装

正式发布版本推荐：

```bash
pip install finchx
```

如果从源码目录安装：

```bash
python -m pip install .
```

本地开发：

```bash
python -m pip install -e ".[dev]"
```

FinchX 要求 Python 3.10 或更高版本，基础运行时依赖 Pydantic 2。

## 快速开始

### 当前行情标的范围

```python
from finchx import FinchX

fx = FinchX()
result = fx.market.quote()

for record in result.data:
    print(record.data["instrumentId"], record.data["price"])
print(result.provider, result.captured_at)
```

### 单只股票行情

```python
result = fx.market.quote_snapshot("600519")
```

单证券 Client 接口既接受完整的 `InstrumentId`，也接受已验证的六位 A 股代码。FinchX 会把代码解析为 `Market.CN_A` + `InstrumentKind.EQUITY`，并在接口支持时按 `6`、`0`/`3`、`4`/`8`/`9` 分别推导 SSE、SZSE、BSE。指数和其他有歧义的标的仍需显式 `InstrumentId`。

### 历史 OHLCV

```python
from datetime import date
from finchx import FinchX
from finchx.datasets import KlineAdjustment

fx = FinchX()
result = fx.market.ohlcv(
    "600519",
    date(2026, 9, 1),
    date(2026, 9, 18),
    adjustment=KlineAdjustment.QFQ,
)
for record in result.data:
    print(record.data["barDate"], record.data["close"])
```

### 新闻与公告

```python
news = fx.news.search("600519", page_size=10)
disclosures = fx.disclosure.search("600519", page_size=10)
print(news.data[0].title if news.data else "no news")
print(disclosures.data[0].title if disclosures.data else "no disclosures")
```

### 财务数据

```python
result = fx.fundamental.financial_summary("600519")
print(result.data.data["periods"])
```

### 股票关键词

`market.stock_keyword` 返回数据源提供的结构化关键词/概念。它不执行 NLP 关键词抽取，也不会虚构热度分数。

```python
result = fx.market.stock_keyword("600519")
for keyword in result.data.data["keywords"]:
    print(keyword["keywordName"], keyword["hitCount"])
```

### 计算偏离值

```python
result = fx.market.deviation("600519", windows=(10, 30))
for window in result.data.windows:
    print(window.window_days, window.deviation)
```

这是基于 FinchX 交易日历和 K 线输入的确定性收盘价计算。它不是交易所官方公告，也不是盘中估算值。版本 1 支持 SSE `60xxxx`、`68xxxx` 以及 SZSE `00xxxx`、`30xxxx` 股票；此能力不支持 BSE。

## 核心概念

### 标的身份

单证券接口既接受完整的 `InstrumentId`，也接受已验证的六位 A 股代码。后者会规范化为 `Market.CN_A` + `InstrumentKind.EQUITY`；代码前缀 `6` 和 `0`/`3` 分别标识 SSE、SZSE。其他有歧义的标的必须提供包含 `code`、`market`、`kind` 以及必要时明确 `exchange` 的完整 `InstrumentId`。

### FetchResult

每个 Client 接口都返回 `FetchResult`。其公开字段包括 `data`、`dataset`、`dataset_id`、`provider`、`provider_id`、`captured_at`、`warnings`、`provenance`、`attempts`、`fallback_used` 和 `cache_hit`。`dataset_id` 与 `provider_id` 分别是 `dataset.name` 与 `provider` 的便捷属性。大多数 Provider-backed 接口把标准化的 `StandardRecord` 对象放入 `data`；搜索接口返回带类型的文档引用元组；计算型偏离值接口直接返回 `DeviationData`。默认展示聚焦业务数据，现有字段和 `StandardRecord` 对象仍完整保留审计元数据。

```python
result = fx.reference.trading_calendar(...)
print(result)
rows = result.to_dicts()
df = result.to_pandas()  # 需要可选的 pandas 包
```

`to_dicts()` 始终返回业务数据字典列表，单条结果也保持这一形式。`to_pandas()` 是可选便捷方法；未安装 pandas 时会给出明确的安装错误。完整契约见 [DATA_API_REFERENCE.zh-CN.md](docs/DATA_API_REFERENCE.zh-CN.md)。

### 快照池接口

EastMoney 的 `limit_up_pool()`、`limit_down_pool()`、`broken_limit_pool()`、`strong_pool()` 和 `yesterday_limit_up_pool()` 接口提供最新可用快照：

```python
result = fx.market.broken_limit_pool()
```

这些接口不承诺历史日期选择。业务数据行会保留 EastMoney 返回的 `tradeDate`；已弃用的 request `tradeDate` 兼容字段不能选择历史日期，传入时会明确拒绝。

### 选择 Provider

使用 `provider=` 可以将请求严格指定到一个已注册的 Provider id：

```python
result = fx.market.quote(provider="tencent.finance.qq.market")
```

这是严格指定：如果指定的 Provider 失败，FinchX 不会静默选择其他 Provider。没有显式指定时，配置的运行时策略会在已实现的 Provider 中进行选择。文档列出已实现的 Provider，但不承诺 primary/fallback 顺序。

### 缓存

缓存由 Collector 配置控制。在启用缓存策略的配置下，`use_cache=None` 遵循该策略，`use_cache=False` 绕过缓存读取。显式指定 Provider 会绕过缓存结果。`FinchX()` 本身不会创建缓存或默认存储文件。

## 可用数据

| Namespace | 提供内容 |
| --- | --- |
| `reference` | 标的身份和交易日历 |
| `market` | 行情、排名、K 线、盘中数据、资金流、涨跌停池、板块、关键词和情绪 |
| `fundamental` | 公司概况、财务摘要、收入和行业比较 |
| `financial` | 财务报表 |
| `news` | 个股新闻引用 |
| `disclosure` | 个股公告引用 |
| `ownership` | 资本和持有人快照 |
| `company` | 管理层快照和持股变动 |
| `corporate_action` | 分红和回购 |

完整的 42 个 Provider-backed / Dataset-backed 公开接口，以及计算型 `market.deviation` 能力，见 [DATA_API_REFERENCE.zh-CN.md](docs/DATA_API_REFERENCE.zh-CN.md)。

## 可选依赖

未安装可选包时，基础安装仍可正常导入。

```bash
python -m pip install ".[calendar]"
python -m pip install ".[jygs]"
```

正式发布版本对应的安装形式为 `pip install "finchx[calendar]"` 和 `pip install "finchx[jygs]"`。

- `calendar` 安装 `pandas_market_calendars`，用于 `pandas_market_calendars` 交易日历 Provider。
- `jygs` 为需要认证的 `jiuyangongshe.daily_replay` Provider 安装 Playwright。该 Provider 还要求提供 `JYGS_SESSION` 值和可用的浏览器安装。

选择缺少可选依赖的能力时会抛出 `MissingOptionalDependency`，并指出所需依赖。

## 错误行为

常见公开错误类别包括：

- `InvalidRequest`：请求值或 Dataset 语义无效。
- `AuthenticationError`：数据源要求凭据或已认证的 session。
- `MissingOptionalDependency`：选定的 Provider 需要尚未安装的 extra。
- `SchemaDrift`：上游响应不再符合 Provider 契约。
- `AllProvidersFailed`：配置的运行时策略允许的所有 Provider 均失败。
- `NoData`：Provider 完成请求但没有产生可用数据。

## 数据来源与第三方说明

FinchX 会对已注册第三方数据源返回的数据进行标准化。它不承诺更新频率、实时可用性或特定的上游服务水平，也不重新分发第三方市场数据集。用户应自行遵守相应数据提供方的条款和政策。

## Python 支持

包元数据声明兼容 Python 3.10、3.11、3.12 和 3.13。Provider 可用性和上游行为可能独立于 Python 版本发生变化。

## 许可证

FinchX 使用 Apache-2.0 许可证。第三方数据和 Provider 条款不包含在 FinchX 许可证中。

## 完整 API 参考

完整的 Dataset 字典、精确方法签名、请求字段、返回字段、Provider 映射、可选依赖和示例，见 [DATA_API_REFERENCE.zh-CN.md](docs/DATA_API_REFERENCE.zh-CN.md)。
