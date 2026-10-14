# FinchX API 参考

安装及可选依赖见 [README](../README.md#安装)。

## 目录

- [通用约定](#common-conventions)
- [基础工具](#basic-reference)
  - [`fx.reference.trading_calendar`](#api-reference-trading_calendar)
  - [`fx.reference.pdf_text`](#api-reference-pdf_text)
- [市场行情](#market-data)
  - [`fx.market.em_breadth`](#api-market-em_breadth)
  - [`fx.market.agp_sentiment`](#api-market-agp_sentiment)
  - [`fx.market.all_quotes`](#api-market-all_quotes)
  - [`fx.market.ranking`](#api-market-ranking)
  - [`fx.market.quote_snapshot`](#api-market-quote_snapshot)
  - [`fx.market.ohlcv`](#api-market-ohlcv)
  - [`fx.market.orderbook`](#api-market-orderbook)
  - [`fx.market.equity_intraday`](#api-market-equity_intraday)
  - [`fx.market.equity_intraday_5d`](#api-market-equity_intraday_5d)
  - [`fx.market.index_intraday`](#api-market-index_intraday)
  - [`fx.market.index_intraday_5d`](#api-market-index_intraday_5d)

- [涨跌停](#limit-pools)
  - [`fx.market.limit_up_pool`](#api-market-limit_up_pool)
  - [`fx.market.limit_down_pool`](#api-market-limit_down_pool)
  - [`fx.market.broken_limit_pool`](#api-market-broken_limit_pool)
  - [`fx.market.yesterday_limit_up_pool`](#api-market-yesterday_limit_up_pool)
  - [`fx.market.strong_pool`](#api-market-strong_pool)
  - [`fx.market.consecutive_limit_up`](#api-market-consecutive_limit_up)

- [资金流](#fund-flow)
  - [`fx.fund_flow.stock`](#api-fund_flow-stock)
  - [`fx.fund_flow.dragon_tiger_list`](#api-fund_flow-dragon_tiger_list)
  - [`fx.fund_flow.dragon_tiger_detail`](#api-fund_flow-dragon_tiger_detail)

- [板块](#sector-data)
  - [`fx.sector.tx_sectors`](#api-sector-tx_sectors)
  - [`fx.sector.em_keywords`](#api-sector-em_keywords)
  - [`fx.sector.tx_industry_comparison`](#api-sector-tx_industry_comparison)
  - [`fx.sector.ths_concept_list`](#api-sector-ths_concept_list)
  - [`fx.sector.ths_concept_quote_snapshot`](#api-sector-ths_concept_quote_snapshot)
  - [`fx.sector.ths_concept_ohlcv`](#api-sector-ths_concept_ohlcv)

- [上市公司信息](#company-data)
  - [`fx.company.info`](#api-company-info)
  - [`fx.company.float_shareholders`](#api-company-float_shareholders)

- [财务](#financial-data)
  - [`fx.financial.statements`](#api-financial-statements)

- [监管](#regulation-data)
  - [`fx.regulation.watchlist`](#api-regulation-watchlist)
  - [`fx.regulation.abnormal_records`](#api-regulation-abnormal_records)
  - [`fx.regulation.abnormal_prediction_history`](#api-regulation-abnormal_prediction_history)
  - [`fx.regulation.severe_predictions`](#api-regulation-severe_predictions)
  - [`fx.regulation.abnormal_counts`](#api-regulation-abnormal_counts)
  - [`fx.regulation.deviation`](#api-regulation-deviation)

- [热榜](#hotlist-data)
  - [`fx.hotlist.stocks`](#api-hotlist-stocks)
  - [`fx.hotlist.sectors`](#api-hotlist-sectors)
  - [`fx.hotlist.convertible_bonds`](#api-hotlist-convertible_bonds)
  - [`fx.hotlist.etfs`](#api-hotlist-etfs)

- [复盘](#fupan-data)
  - [`fx.fupan.jygs_replay`](#api-fupan-jygs_replay)

- [新闻](#news-data)
  - [`fx.news.agp_list`](#api-news-agp_list)
  - [`fx.news.bd_list`](#api-news-bd_list)
  - [`fx.news.em_list`](#api-news-em_list)
  - [`fx.news.em_get`](#api-news-em_get)

- [文章](#articles-data)
  - [`fx.articles.hot_content`](#api-articles-hot_content)
  - [`fx.articles.ths_list`](#api-articles-ths_list)
  - [`fx.articles.ths_get`](#api-articles-ths_get)
  - [`fx.articles.agp_topic_articles`](#api-articles-agp_topic_articles)
  - [`fx.articles.agp_get`](#api-articles-agp_get)

- [公告](#disclosure-data)
  - [`fx.disclosure.em_list`](#api-disclosure-em_list)
  - [`fx.disclosure.em_get`](#api-disclosure-em_get)

- [研报](#reports-data)
  - [`fx.reports.fetch`](#api-reports-fetch)
  - [`fx.reports.agp_list`](#api-reports-agp_list)
  - [`fx.reports.agp_get`](#api-reports-agp_get)

- [论坛](#forum-data)
  - [`fx.forum.tgb_replies`](#api-forum-tgb_replies)

- [问财](#iwencai-data)
  - [`fx.iwencai.select`](#api-iwencai-select)
  - [`fx.iwencai.search`](#api-iwencai-search)
  - [`fx.iwencai.get_report`](#api-iwencai-get_report)

<a id="common-conventions"></a>
## 通用约定

数字缺失为 Python `None`（JSON `null`），有效 `0` 保留；可选列表缺失为 `None`，明确为空时为 `[]`。百分数字段的 `1.23` 表示 `1.23%`，其他单位及币种见字段说明。

`FinchX(timeout=15.0)` 设置每次 HTTP 请求的超时秒数，须为有限正数 `int` 或 `float`；整数参数及 timeout 均不接受布尔值。每次调用重新取数，不缓存；Cookie、API Key 与 SESSION 仅用于当次调用。

参数错误抛出 `ValueError`；来源读取失败或必要数据不可用时抛出 `SourceError` 或 `FinchXError`，均可从 `finchx` 导入，不返回部分数据冒充正常结果。

日期与时刻字符串支持 `YYYY-MM-DD`、`YYYYMMDD`、`YYYY/MM/DD`，以及这三种日期各自加空格和完整 `HH:MM:SS`。按北京时间解释，须为合法 ASCII 日期与时刻，不接受额外空白、时区、部分时刻或小数秒；按天查询只取日期。`datetime.date` 支持情况见参数类型列，日期参数均不接受 `datetime` 对象。

<a id="basic-reference"></a>
## 基础工具

<a id="api-reference-trading_calendar"></a>
### `fx.reference.trading_calendar`

获取日期范围内每个自然日的 A 股交易日标记，按日期升序返回，包含首尾日期。

来源：[深交所交易日历](https://www.szse.cn/aboutus/calendar/)，备用来源为 [`pandas_market_calendars`](https://pandas-market-calendars.readthedocs.io/) 的 SSE 离线日历。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `start_date` | `str \| datetime.date` | 必需 | — | 开始日期，包含当日；接受 `datetime.date` 或[通用约定](#common-conventions)中的日期与时刻字符串。 |
| `end_date` | `str \| datetime.date` | 必需 | — | 结束日期，包含当日；类型及格式同上，不得早于 `start_date`。 |
| `source` | `str` | 可选，仅限关键字 | `"auto"` | `"auto"`：首选深交所，失败后整段回退离线日历；`"szse"`：仅深交所；`"pandas_market_calendars"`：仅离线日历。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 自然日，格式为 `YYYY-MM-DD`。 |
| `is_trading_day` | `bool` | `true` 为交易日，`false` 为休市日。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.reference.trading_calendar(
    start_date="2026-09-17",
    end_date="2026-09-19",
    source="szse",
)
```

```json
[
  {
    "date": "2026-09-17",
    "is_trading_day": true
  },
  {
    "date": "2026-09-18",
    "is_trading_day": true
  },
  {
    "date": "2026-09-19",
    "is_trading_day": false
  }
]
```

省略 `source` 即使用默认的 `"auto"`；安装可选日历依赖后，可传 `source="pandas_market_calendars"` 使用离线日历，返回格式相同。

默认自动回退成功时，通过标准 `UserWarning` 提示整段改用离线日历及原因；正常成功不提示。显式指定来源时不回退。

离线日历按安装的库版本生成；未公布正式休市安排的年份可能使用估算规则，不能视为交易所已公布安排。

<a id="api-reference-pdf_text"></a>
### `fx.reference.pdf_text`

读取 PDF 链接的原生书签目录与全部页面文字，便于定位、引用和选择需要阅读的页面。可使用公告 `attachments` 或研报 `pdf_urls` 中的 PDF 链接。

来源：调用者提供的 PDF 文件；使用 [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) 提取。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | HTTP/HTTPS 绝对 PDF 链接，支持合法查询参数和显式端口；不要求链接以 .pdf 结尾，不接受认证信息、空白或控制字符。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `outline` | `list[dict]` | 按 PDF 原生书签顺序返回，无书签为 []。 |
| `outline[].title` | `str` | 原生书签标题。 |
| `outline[].page_number` | `int \| None` | 目标 PDF 实际页码，从 1 开始；无本地页面目标为 None。 |
| `pages` | `list[dict]` | 全部页面，按实际页序返回。 |
| `pages[].page_number` | `int` | PDF 实际页码，从 1 开始。 |
| `pages[].content` | `str` | 本页可提取文字，保留原文并规范换行；无文字时为空字符串。 |

**调用与返回示例**

```python
result = fx.reference.pdf_text(
    url="https://pdf.dfcfw.com/pdf/H2_AN202609301830044481_1.pdf?1790785457000.pdf"
)
```

```text
{
  "outline": [
    {"title": "一、股份转让的基本情况", "page_number": 1},
    {"title": "二、股份过户登记情况", "page_number": 1},
    {"title": "三、备查文件 ", "page_number": 2}
  ],
  "pages": [
    {
      "page_number": 1,
      "content": "证券代码：300308 证券简称：中际旭创 公告编号：2026-099\n中际旭创股份有限公司\n关于协议受让北京中石伟业科技股份有限公司部分股权\n完成过户登记的公告\n一、股份转让的基本情况\n..."
    },
    {
      "page_number": 2,
      "content": "三、备查文件\n1、中国证券登记结算有限责任公司出具的《证券过户登记确认书》。\n特此公告\n中际旭创股份有限公司董事会\n2026 年 10 月 01 日"
    }
  ]
}
```

**必要限制**

需安装可选 PDF 依赖，见 [README](../README.md#安装)。客户端 timeout 仅控制下载请求，不限制本地解析耗时。

仅提取已有文字层，不做 OCR、章节推断、摘要或表格结构化；页眉、页脚及文字层中的模板文字保留，不保证复杂版式的阅读顺序。空白页或无文字层页保留。全文提取结果不含任何 Unicode 文字或数字，仅有空白、符号、私用区图标或替换占位时抛出 SourceError；有文字或数字时，各页符号均原样保留。图像或图形化正文需要 OCR 才能读取，少量可提取文字不代表正文完整。需密码且无法直接打开的 PDF 不支持。

提取结果中的个别字符若存在 UTF-16 编码异常，保留有效文字，将无法解码的符号显示为 `�`；成功后通过一条标准 UserWarning 提示涉及页码，不推断原符号。其他下载或解析失败仍整次报错，不返回部分页面。

目录只来自原生书签，可能缺失或不适合作为章节目录。同一页可有多个书签，返回页码不保证对应准确章节边界；一次将全部页面文字送给 AI，仍会占用全文输入量。

<a id="market-data"></a>
## 市场行情

<a id="api-market-em_breadth"></a>
### `fx.market.em_breadth`

获取市场上涨、下跌家数及涨跌幅分布。

来源：东方财富。

**参数**

无。

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源统计日期，YYYY-MM-DD。 |
| `advancing` | `int` | 上涨家数。 |
| `declining` | `int` | 下跌家数。 |
| `unchanged` | `int` | 平盘家数。 |
| `total` | `int` | 统计总家数。 |
| `limit_up_count` | `int` | 涨停家数。 |
| `limit_down_count` | `int` | 跌停家数。 |
| `up_over_9_percent_count` | `int` | 高于 9% 且未涨停的家数。 |
| `down_over_9_percent_count` | `int` | 低于 -9% 且未跌停的家数。 |
| `distribution` | `list[dict]` | 按来源区间排列的涨跌分布。 |
| `distribution[].range` | `str` | 来源中文区间标签。 |
| `distribution[].count` | `int` | 该区间家数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.em_breadth()
```

```text
{
  "date": "2026-10-08",
  "advancing": 1644,
  "declining": 3615,
  "unchanged": 101,
  "total": 5360,
  "limit_up_count": 43,
  "limit_down_count": 14,
  "up_over_9_percent_count": 22,
  "down_over_9_percent_count": 50,
  "distribution": [
    {
      "range": "跌停",
      "count": 14
    },
    {
      "range": "低于-9%(未跌停)",
      "count": 50
    },
    ...
  ]
}
```

统计范围及区间按东方财富口径，不能与其他来源的股票集合直接等同。

<a id="api-market-agp_sentiment"></a>
### `fx.market.agp_sentiment`

获取市场情绪指标。

来源：爱股票。

**参数**

无。

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `market_temperature` | `float \| None` | 来源情绪评分。 |
| `total_turnover` | `float \| None` | 市场总成交额，元。 |
| `forecasted_turnover` | `float \| None` | 来源预测成交额，元。 |
| `turnover_change_amount` | `float \| None` | 较前一日成交额变动，元。 |
| `turnover_change_percent` | `float \| None` | 成交额变化幅度，%。 |
| `median_change_percent` | `float \| None` | 涨跌幅中位数，%。 |
| `blast_break_percent` | `float \| None` | 炸板率，%。 |
| `previous_limit_up_break_change_percent` | `float \| None` | 前期炸板股表现，%。 |
| `two_limit_up_promotion_percent` | `float \| None` | 二板晋级率，%。 |
| `three_limit_up_promotion_percent` | `float \| None` | 三板晋级率，%。 |
| `high_limit_up_promotion_percent` | `float \| None` | 高连板晋级率，%。 |
| `previous_limit_up_theme_change_percent` | `float \| None` | 前期涨停组表现，%。 |
| `previous_consecutive_limit_up_theme_change_percent` | `float \| None` | 前期连板组表现，%。 |
| `stop_trading_count` | `int \| None` | 停牌家数。 |
| `one_limit_up_count` | `int \| None` | 一板家数。 |
| `two_limit_up_count` | `int \| None` | 二板家数。 |
| `three_limit_up_count` | `int \| None` | 三板家数。 |
| `high_limit_up_count` | `int \| None` | 高连板家数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.agp_sentiment()
```

```json
{
  "market_temperature": 30.0,
  "total_turnover": 1680000000000.0,
  "forecasted_turnover": null,
  "turnover_change_amount": 244100000000.0,
  "turnover_change_percent": null,
  "median_change_percent": -1.01,
  "blast_break_percent": 45.0,
  "previous_limit_up_break_change_percent": -4.44,
  "two_limit_up_promotion_percent": 6.0,
  "three_limit_up_promotion_percent": 66.0,
  "high_limit_up_promotion_percent": 42.0,
  "previous_limit_up_theme_change_percent": 0.12,
  "previous_consecutive_limit_up_theme_change_percent": 5.09,
  "stop_trading_count": 15,
  "one_limit_up_count": 32,
  "two_limit_up_count": 3,
  "three_limit_up_count": 4,
  "high_limit_up_count": 3
}
```

情绪评分、预测成交额及晋级率采用来源口径，不提供历史日期查询。

<a id="api-market-all_quotes"></a>
### `fx.market.all_quotes`

获取腾讯财经提供的沪深北 A 股行情。

来源：腾讯财经。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码，保留前导零。 |
| `exchange` | `str` | `sh` 上海、`sz` 深圳、`bj` 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 最新价，元/股。 |
| `price_change` | `float \| None` | 价格涨跌额，元/股。 |
| `change_percent` | `float \| None` | 当日涨跌幅，%。 |
| `change_percent_5d` | `float \| None` | 5 日涨跌幅，%。 |
| `change_percent_10d` | `float \| None` | 10 日涨跌幅，%。 |
| `change_percent_20d` | `float \| None` | 20 日涨跌幅，%。 |
| `change_percent_60d` | `float \| None` | 60 日涨跌幅，%。 |
| `change_percent_52w` | `float \| None` | 52 周涨跌幅，%。 |
| `change_percent_ytd` | `float \| None` | 年初至今涨跌幅，%。 |
| `amplitude` | `float \| None` | 振幅，%。 |
| `turnover_rate` | `float \| None` | 换手率，%。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `main_net_inflow` | `float \| None` | 主力净流入，元。 |
| `main_inflow` | `float \| None` | 主力流入，元。 |
| `main_outflow` | `float \| None` | 主力流出，元。 |
| `main_inflow_5d` | `float \| None` | 5 日主力流入，元。 |
| `main_outflow_5d` | `float \| None` | 5 日主力流出，元。 |
| `pe_ttm` | `float \| None` | 滚动市盈率，倍。 |
| `volume_ratio` | `float \| None` | 量比，倍。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.all_quotes()
```

```text
[
  {
    "code": "300308",
    "exchange": "sz",
    "name": "中际旭创",
    "price": 780.66,
    "price_change": -27.78,
    "change_percent": -3.44,
    "volume": 26449900,
    "amount": 21109500000.0,
    "turnover_rate": 2.38,
    "market_cap": 919547000000.0,
    "float_market_cap": 866483000000.0,
    "pe_ttm": 44.96,
    "change_percent_5d": -15.38,
    "change_percent_10d": -14.01,
    "change_percent_20d": -5.08,
    "change_percent_60d": -30.81,
    "change_percent_52w": 94.06,
    "change_percent_ytd": 28.19,
    "amplitude": 7.71,
    "volume_ratio": 1.41,
    "main_net_inflow": -1517483200.0,
    "main_inflow": 12905369700.0,
    "main_outflow": 14422852900.0,
    "main_inflow_5d": 51518716200.0,
    "main_outflow_5d": 59282486000.0
  },
  ...
]
```

证券范围按来源返回，不保证覆盖所有上市证券；保留 ST 和零成交记录。分页期间行情会变化，不能视为同一时点快照。

<a id="api-market-ranking"></a>
### `fx.market.ranking`

按成交额、涨跌幅或成交量获取股票排名。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `criterion` | `str` | 可选 | `"change_percent"` | `"amount"` 成交额、`"change_percent"` 涨跌幅、`"volume"` 成交量。 |
| `direction` | `str` | 可选 | `"desc"` | `"desc"` 降序、`"asc"` 升序。 |
| `limit` | `int \| None` | 可选 | `50` | 正整数返回前若干条；`None` 返回全部，不接受布尔值。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码，保留前导零。 |
| `exchange` | `str` | `sh` 上海、`sz` 深圳、`bj` 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 最新价，元/股。 |
| `price_change` | `float \| None` | 价格涨跌额，元/股。 |
| `change_percent` | `float \| None` | 当日涨跌幅，%。 |
| `change_percent_5d` | `float \| None` | 5 日涨跌幅，%。 |
| `change_percent_10d` | `float \| None` | 10 日涨跌幅，%。 |
| `change_percent_20d` | `float \| None` | 20 日涨跌幅，%。 |
| `change_percent_60d` | `float \| None` | 60 日涨跌幅，%。 |
| `change_percent_52w` | `float \| None` | 52 周涨跌幅，%。 |
| `change_percent_ytd` | `float \| None` | 年初至今涨跌幅，%。 |
| `amplitude` | `float \| None` | 振幅，%。 |
| `turnover_rate` | `float \| None` | 换手率，%。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `main_net_inflow` | `float \| None` | 主力净流入，元。 |
| `main_inflow` | `float \| None` | 主力流入，元。 |
| `main_outflow` | `float \| None` | 主力流出，元。 |
| `main_inflow_5d` | `float \| None` | 5 日主力流入，元。 |
| `main_outflow_5d` | `float \| None` | 5 日主力流出，元。 |
| `pe_ttm` | `float \| None` | 滚动市盈率，倍。 |
| `volume_ratio` | `float \| None` | 量比，倍。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.ranking(criterion="change_percent", direction="desc", limit=5)
```

```text
[
  {
    "code": "920627",
    "exchange": "bj",
    "name": "力王股份",
    "price": 17.83,
    "price_change": 4.11,
    "change_percent": 29.96,
    "volume": 12613200,
    "amount": 213940000.0,
    "turnover_rate": 25.69,
    "market_cap": 1684000000.0,
    "float_market_cap": 875000000.0,
    "pe_ttm": 77.55,
    "change_percent_5d": 32.86,
    "change_percent_10d": 32.07,
    "change_percent_20d": 20.55,
    "change_percent_60d": 15.85,
    "change_percent_52w": -36.21,
    "change_percent_ytd": -16.05,
    "amplitude": 31.34,
    "volume_ratio": 9.01,
    "main_net_inflow": 0.0,
    "main_inflow": 0.0,
    "main_outflow": 0.0,
    "main_inflow_5d": 0.0,
    "main_outflow_5d": 0.0
  },
  ...
]
```

排名由腾讯来源按所选字段和方向排序。有限 `limit` 只读取足够的来源排名页以取得目标数量的唯一股票；若来源总数小于 `limit`，返回全部可用记录。实时变动造成跨页重复时，仅沿用同一来源排序补取，最多重新读取三轮，仍不足则报错。`limit=None` 才读取完整股票集合。返回前仍按规范化数值排序，缺失值置末，同值按交易所和代码稳定排列。

<a id="api-market-quote_snapshot"></a>
### `fx.market.quote_snapshot`

获取单只股票或指数的行情快照。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 字符串；股票支持沪市 60/68、深市 00/30 开头；指数支持 `000001`、`000002`、`000688`、`399001`、`399006`、`399102`、`399107`。 |
| `kind` | `str` | 可选，仅限关键字 | `"stock"` | `"stock"` 股票、`"index"` 指数。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳。 |
| `name` | `str \| None` | 证券或指数名称。 |
| `time` | `str \| None` | 来源行情时间，含 +08:00 时区；缺失为 None。 |
| `price` | `float \| None` | 最新价；股票元/股，指数点。 |
| `previous_close` | `float \| None` | 昨收；股票元/股，指数点。 |
| `open` | `float \| None` | 今开；股票元/股，指数点。 |
| `high` | `float \| None` | 最高；股票元/股，指数点。 |
| `low` | `float \| None` | 最低；股票元/股，指数点。 |
| `price_change` | `float \| None` | 价格涨跌额；股票元/股，指数点。 |
| `change_percent` | `float \| None` | 涨跌幅，%。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.quote_snapshot(code="600519", kind="stock")
```

```json
{
  "code": "600519",
  "exchange": "sh",
  "name": "贵州茅台",
  "time": "2026-10-08T15:03:17+08:00",
  "price": 1255.79,
  "previous_close": 1258.62,
  "open": 1252.9,
  "high": 1258.0,
  "low": 1242.0,
  "price_change": -2.83,
  "change_percent": -0.22,
  "volume": 2516800,
  "amount": 3145413157.0
}
```

股票和指数以 kind 区分，例如 `code="000001", kind="index"` 为上证指数。行情时间来自来源，不代表调用时刻。

<a id="api-market-ohlcv"></a>
### `fx.market.ohlcv`

获取包含首尾日期范围的日线，按日期升序返回。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 字符串；股票支持沪市 60/68、深市 00/30 开头；指数支持 `000001`、`000002`、`000688`、`399001`、`399006`、`399102`、`399107`。 |
| `start_date` | `str \| datetime.date` | 必需 | — | 开始日期，包含当日；接受 `datetime.date` 或[通用约定](#common-conventions)中的日期与时刻字符串。 |
| `end_date` | `str \| datetime.date` | 必需 | — | 结束日期，包含当日；不得早于 start_date。 |
| `adjustment` | `str \| None` | 可选 | `None` | `None` 不复权、`"qfq"` 前复权、`"hfq"` 后复权；指数只能为 None。 |
| `kind` | `str` | 可选，仅限关键字 | `"stock"` | `"stock"` 股票、`"index"` 指数。 |

请求 `"qfq"` 时，仅在同份来源响应完全缺少 `qfqday` 键且提供合法 `day` 序列时，返回该不复权日线，近似当作无需复权，并在整次成功后发出一条标准中文 `UserWarning`。不检查分红或除权，也不追加其他来源请求。已存在但为空的 `qfqday` 保持空结果；None、非法类型或损坏序列明确失败，不回退。后复权不回退；多页实际复权口径不一致时整次失败，返回行不增加口径字段。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 交易日期，YYYY-MM-DD。 |
| `open` | `float \| None` | 开盘价；股票元/股，指数点。 |
| `high` | `float \| None` | 最高价；股票元/股，指数点。 |
| `low` | `float \| None` | 最低价；股票元/股，指数点。 |
| `close` | `float \| None` | 收盘价；股票元/股，指数点。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元；来源未提供则为 None。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.ohlcv(
    code="600519",
    start_date="2026-09-17",
    end_date="2026-09-19",
    adjustment=None,
    kind="stock",
)
```

```json
[
  {
    "date": "2026-09-17",
    "open": 1257.98,
    "high": 1267.6,
    "low": 1254.0,
    "close": 1266.98,
    "volume": 1755400,
    "amount": 2217338300.0
  },
  {
    "date": "2026-09-18",
    "open": 1262.99,
    "high": 1265.88,
    "low": 1256.1,
    "close": 1257.12,
    "volume": 2489100,
    "amount": 3135849100.0
  }
]
```

仅返回来源存在的交易日，不补休市日或缺失历史；复权采用来源日线，指数不支持复权。

<a id="api-market-orderbook"></a>
### `fx.market.orderbook`

获取股票买卖五档盘口。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 沪市 60/68、深市 00/30 开头的六位 ASCII 股票代码。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳。 |
| `name` | `str \| None` | 证券名称。 |
| `time` | `str \| None` | 来源行情时间，含 +08:00 时区；缺失为 None。 |
| `bids` | `list[dict]` | 买一至买五。 |
| `asks` | `list[dict]` | 卖一至卖五。 |

bids 与 asks 中的档位字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `level` | `int` | 档位，1 至 5。 |
| `price` | `float \| None` | 该档价格，元/股。 |
| `volume` | `int \| None` | 该档委托量，股。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.orderbook(code="600519")
```

```json
{
  "code": "600519",
  "exchange": "sh",
  "name": "贵州茅台",
  "time": "2026-10-08T15:03:17+08:00",
  "bids": [
    {
      "level": 1,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 2,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 3,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 4,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 5,
      "price": 0.0,
      "volume": 0
    }
  ],
  "asks": [
    {
      "level": 1,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 2,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 3,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 4,
      "price": 0.0,
      "volume": 0
    },
    {
      "level": 5,
      "price": 0.0,
      "volume": 0
    }
  ]
}
```

仅支持股票；零档位及缺失值均保留。

<a id="api-market-equity_intraday"></a>
### `fx.market.equity_intraday`

获取股票最近一个来源交易日的分时行情。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 沪市 60/68、深市 00/30 开头的六位 ASCII 股票代码。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日期，YYYY-MM-DD。 |
| `time` | `str` | 来源时刻，HH:MM。 |
| `price` | `float \| None` | 价格，元/股。 |
| `volume` | `int \| None` | 相邻来源点累计成交量之差，股。 |
| `amount` | `float \| None` | 相邻来源点累计成交额之差，元。 |
| `cumulative_volume` | `int \| None` | 当日累计成交量，股。 |
| `cumulative_amount` | `float \| None` | 当日累计成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.equity_intraday(code="600519")
```

```text
[
  {
    "date": "2026-10-08",
    "time": "09:30",
    "price": 1252.9,
    "volume": 36800,
    "amount": 46106719.6,
    "cumulative_volume": 36800,
    "cumulative_amount": 46106719.6
  },
  {
    "date": "2026-10-08",
    "time": "09:31",
    "price": 1245.78,
    "volume": 140100,
    "amount": 174705879.63,
    "cumulative_volume": 176900,
    "cumulative_amount": 220812599.23
  },
  ...
]
```

按日期和时间升序；每日首点量额使用当日累计值，之后为相邻来源点差额，缺值无法差分时为 None。来源点不一定间隔一分钟，不补交易日或时间空白。

<a id="api-market-equity_intraday_5d"></a>
### `fx.market.equity_intraday_5d`

获取股票最近最多五个来源交易日的分时行情。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 沪市 60/68、深市 00/30 开头的六位 ASCII 股票代码。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日期，YYYY-MM-DD。 |
| `time` | `str` | 来源时刻，HH:MM。 |
| `price` | `float \| None` | 价格，元/股。 |
| `volume` | `int \| None` | 相邻来源点累计成交量之差，股。 |
| `amount` | `float \| None` | 相邻来源点累计成交额之差，元。 |
| `cumulative_volume` | `int \| None` | 当日累计成交量，股。 |
| `cumulative_amount` | `float \| None` | 当日累计成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.equity_intraday_5d(code="600519")
```

```text
[
  {
    "date": "2026-09-24",
    "time": "09:30",
    "price": 1250.01,
    "volume": 18300,
    "amount": 22875182.71,
    "cumulative_volume": 18300,
    "cumulative_amount": 22875182.71
  },
  {
    "date": "2026-09-24",
    "time": "09:31",
    "price": 1249.99,
    "volume": 121000,
    "amount": 151247716.66,
    "cumulative_volume": 139300,
    "cumulative_amount": 174122899.37
  },
  ...
]
```

按日期和时间升序；每日首点量额使用当日累计值，之后为相邻来源点差额，缺值无法差分时为 None。来源点不一定间隔一分钟，不补交易日或时间空白。

<a id="api-market-index_intraday"></a>
### `fx.market.index_intraday`

获取指数最近一个来源交易日的分时行情。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 仅支持六位 ASCII 字符串：`000001` 上证指数、`399001` 深证成指、`399006` 创业板指。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日期，YYYY-MM-DD。 |
| `time` | `str` | 来源时刻，HH:MM。 |
| `price` | `float \| None` | 指数点。 |
| `volume` | `int \| None` | 相邻来源点累计成交量之差，股。 |
| `amount` | `float \| None` | 相邻来源点累计成交额之差，元。 |
| `cumulative_volume` | `int \| None` | 当日累计成交量，股。 |
| `cumulative_amount` | `float \| None` | 当日累计成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.index_intraday(code="000001")
```

```text
[
  {
    "date": "2026-10-08",
    "time": "09:30",
    "price": 3838.98,
    "volume": 429824300,
    "amount": 6743785034.4,
    "cumulative_volume": 429824300,
    "cumulative_amount": 6743785034.4
  },
  {
    "date": "2026-10-08",
    "time": "09:31",
    "price": 3837.88,
    "volume": 1822524700,
    "amount": 30264358941.8,
    "cumulative_volume": 2252349000,
    "cumulative_amount": 37008143976.2
  },
  ...
]
```

按日期和时间升序；每日首点量额使用当日累计值，之后为相邻来源点差额，缺值无法差分时为 None。来源点不一定间隔一分钟，不补交易日或时间空白。

<a id="api-market-index_intraday_5d"></a>
### `fx.market.index_intraday_5d`

获取指数最近最多五个来源交易日的分时行情。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 仅支持六位 ASCII 字符串：`000001` 上证指数、`399001` 深证成指、`399006` 创业板指。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日期，YYYY-MM-DD。 |
| `time` | `str` | 来源时刻，HH:MM。 |
| `price` | `float \| None` | 指数点。 |
| `volume` | `int \| None` | 相邻来源点累计成交量之差，股。 |
| `amount` | `float \| None` | 相邻来源点累计成交额之差，元。 |
| `cumulative_volume` | `int \| None` | 当日累计成交量，股。 |
| `cumulative_amount` | `float \| None` | 当日累计成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
fx.market.index_intraday_5d(code="000001")
```

```text
[
  {
    "date": "2026-09-24",
    "time": "09:30",
    "price": 3925.32,
    "volume": 409855300,
    "amount": 5934196660.3,
    "cumulative_volume": 409855300,
    "cumulative_amount": 5934196660.3
  },
  {
    "date": "2026-09-24",
    "time": "09:31",
    "price": 3921.49,
    "volume": 1751109000,
    "amount": 28170554593.6,
    "cumulative_volume": 2160964300,
    "cumulative_amount": 34104751253.9
  },
  ...
]
```

按日期和时间升序；每日首点量额使用当日累计值，之后为相邻来源点差额，缺值无法差分时为 None。来源点不一定间隔一分钟，不补交易日或时间空白。

<a id="limit-pools"></a>
## 涨跌停

东方财富五个股池按来源最新观察日期返回，按代码升序，不支持指定历史日期。来源时间为 0 时表示未提供，返回 None。来源范围及入池口径以各池说明为准。

<a id="api-market-limit_up_pool"></a>
### `fx.market.limit_up_pool`

获取最新涨停股池。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源当前观察日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 当前价格，元/股。 |
| `change_percent` | `float \| None` | 当前涨跌幅，%。 |
| `amount` | `float \| None` | 当前成交额，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `turnover_rate` | `float \| None` | 当前换手率，%。 |
| `industry` | `str \| None` | 来源行业名称。 |
| `consecutive_limit_up_days` | `int \| None` | 连续涨停天数。 |
| `first_limit_up_time` | `str \| None` | 首次涨停时刻，HH:MM:SS。 |
| `last_limit_up_time` | `str \| None` | 最后涨停时刻，HH:MM:SS。 |
| `limit_up_queue_amount` | `float \| None` | 来源涨停封单金额，元。 |
| `limit_up_break_count` | `int \| None` | 炸板次数。 |
| `limit_up_stats_days` | `int \| None` | 来源统计窗口，天。 |
| `limit_up_stats_count` | `int \| None` | 该股票窗口内涨停次数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.limit_up_pool()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "000869",
    "exchange": "sz",
    "name": "张  裕Ａ",
    "price": 18.76,
    "change_percent": 10.029325485229492,
    "amount": 140803249.0,
    "float_market_cap": 8536843431.200001,
    "market_cap": 12067935201.28,
    "turnover_rate": 1.6902669668197632,
    "industry": "非白酒",
    "limit_up_stats_days": 1,
    "limit_up_stats_count": 1,
    "consecutive_limit_up_days": 1,
    "first_limit_up_time": "10:43:00",
    "last_limit_up_time": "10:43:00",
    "limit_up_queue_amount": 19521074.0,
    "limit_up_break_count": 0
  },
  ...
]
```

<a id="api-market-limit_down_pool"></a>
### `fx.market.limit_down_pool`

获取最新跌停股池。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源当前观察日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 当前价格，元/股。 |
| `change_percent` | `float \| None` | 当前涨跌幅，%。 |
| `amount` | `float \| None` | 当前成交额，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `turnover_rate` | `float \| None` | 当前换手率，%。 |
| `industry` | `str \| None` | 来源行业名称。 |
| `pe` | `float \| None` | 来源动态市盈率，倍。 |
| `limit_down_queue_amount` | `float \| None` | 来源跌停排队金额，元。 |
| `last_limit_down_time` | `str \| None` | 最后跌停时刻，HH:MM:SS。 |
| `board_traded_amount` | `float \| None` | 以跌停价成交的金额，元。 |
| `consecutive_limit_down_days` | `int \| None` | 连续跌停天数。 |
| `limit_down_open_count` | `int \| None` | 跌停开板次数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.limit_down_pool()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "000513",
    "exchange": "sz",
    "name": "丽珠集团",
    "price": 29.61,
    "change_percent": -10.0,
    "amount": 1064992544.0,
    "float_market_cap": 16808169442.68,
    "market_cap": 26290931244.48,
    "turnover_rate": 6.150713920593262,
    "industry": "化学制药",
    "pe": 14.101563453674316,
    "limit_down_queue_amount": 2060856.0,
    "last_limit_down_time": "14:24:00",
    "board_traded_amount": 85013890.0,
    "consecutive_limit_down_days": 1,
    "limit_down_open_count": 18
  },
  ...
]
```

<a id="api-market-broken_limit_pool"></a>
### `fx.market.broken_limit_pool`

获取最新炸板股池。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源当前观察日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 当前价格，元/股。 |
| `change_percent` | `float \| None` | 当前涨跌幅，%。 |
| `amount` | `float \| None` | 当前成交额，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `turnover_rate` | `float \| None` | 当前换手率，%。 |
| `industry` | `str \| None` | 来源行业名称。 |
| `limit_up_price` | `float \| None` | 当前涨停价，元/股。 |
| `amplitude` | `float \| None` | 当前振幅，%。 |
| `change_speed_percent` | `float \| None` | 来源涨速，%。 |
| `first_limit_up_time` | `str \| None` | 首次涨停时刻，HH:MM:SS。 |
| `limit_up_break_count` | `int \| None` | 炸板次数。 |
| `limit_up_stats_days` | `int \| None` | 来源统计窗口，天。 |
| `limit_up_stats_count` | `int \| None` | 该股票窗口内涨停次数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.broken_limit_pool()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "000011",
    "exchange": "sz",
    "name": "深物业A",
    "price": 12.12,
    "change_percent": -0.9803922176361084,
    "amount": 1513302208.0,
    "float_market_cap": 6380883581.16,
    "market_cap": 7223266546.559999,
    "turnover_rate": 22.1230525970459,
    "industry": "房地产开",
    "limit_up_stats_days": 4,
    "limit_up_stats_count": 3,
    "limit_up_price": 13.46,
    "change_speed_percent": 0.0,
    "amplitude": 10.947712898254395,
    "first_limit_up_time": "09:31:03",
    "limit_up_break_count": 7
  },
  ...
]
```

炸板次数及涨速按来源口径。

<a id="api-market-yesterday_limit_up_pool"></a>
### `fx.market.yesterday_limit_up_pool`

获取昨日涨停股在当前来源观察日的行情。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源当前观察日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 当前价格，元/股。 |
| `change_percent` | `float \| None` | 当前涨跌幅，%。 |
| `amount` | `float \| None` | 当前成交额，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `turnover_rate` | `float \| None` | 当前换手率，%。 |
| `industry` | `str \| None` | 来源行业名称。 |
| `limit_up_price` | `float \| None` | 当前涨停价，元/股。 |
| `amplitude` | `float \| None` | 当前振幅，%。 |
| `change_speed_percent` | `float \| None` | 来源涨速，%。 |
| `yesterday_first_limit_up_time` | `str \| None` | 前一交易日首次涨停时刻，HH:MM:SS。 |
| `yesterday_consecutive_limit_up_days` | `int \| None` | 前一交易日连续涨停天数。 |
| `limit_up_stats_days` | `int \| None` | 来源统计窗口，天。 |
| `limit_up_stats_count` | `int \| None` | 该股票窗口内涨停次数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.yesterday_limit_up_pool()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "000011",
    "exchange": "sz",
    "name": "深物业A",
    "price": 12.12,
    "change_percent": -0.9803922176361084,
    "amount": 1513302208.0,
    "float_market_cap": 6380883581.16,
    "market_cap": 7223266546.559999,
    "turnover_rate": 22.1230525970459,
    "industry": "房地产开",
    "limit_up_stats_days": 4,
    "limit_up_stats_count": 3,
    "limit_up_price": 13.46,
    "change_speed_percent": 0.0,
    "amplitude": 10.947712898254395,
    "yesterday_first_limit_up_time": "13:11:24",
    "yesterday_consecutive_limit_up_days": 3
  },
  ...
]
```

date 是当前观察日期；yesterday 开头的字段才描述前一交易日的涨停事件。

<a id="api-market-strong_pool"></a>
### `fx.market.strong_pool`

获取来源筛选的最新强势股池。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源当前观察日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 当前价格，元/股。 |
| `change_percent` | `float \| None` | 当前涨跌幅，%。 |
| `amount` | `float \| None` | 当前成交额，元。 |
| `float_market_cap` | `float \| None` | 流通市值，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `turnover_rate` | `float \| None` | 当前换手率，%。 |
| `industry` | `str \| None` | 来源行业名称。 |
| `limit_up_price` | `float \| None` | 当前涨停价，元/股。 |
| `is_sixty_day_high` | `bool \| None` | 来源是否标记为 60 日新高。 |
| `selection_reason` | `str \| None` | 来源中文入选原因。 |
| `volume_ratio` | `float \| None` | 量比，倍。 |
| `change_speed_percent` | `float \| None` | 来源涨速，%。 |
| `limit_up_stats_days` | `int \| None` | 来源统计窗口，天。 |
| `limit_up_stats_count` | `int \| None` | 该股票窗口内涨停次数。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.strong_pool()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "000001",
    "exchange": "sz",
    "name": "平安银行",
    "price": 11.78,
    "change_percent": 1.8150389194488525,
    "amount": 1743402512.0,
    "float_market_cap": 228598969193.97998,
    "market_cap": 228601716490.24,
    "turnover_rate": 0.7635318636894226,
    "industry": "银行Ⅱ",
    "limit_up_stats_days": 0,
    "limit_up_stats_count": 0,
    "limit_up_price": 12.73,
    "change_speed_percent": 0.0,
    "is_sixty_day_high": true,
    "selection_reason": "60日新高",
    "volume_ratio": 1.819536805152893
  },
  ...
]
```

入选原因及 60 日新高标记按来源定义。

<a id="api-market-consecutive_limit_up"></a>
### `fx.market.consecutive_limit_up`

获取来源提供的连板股行情。

来源：爱股票。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日期，YYYY-MM-DD。 |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh 上海、sz 深圳、bj 北京。 |
| `name` | `str \| None` | 证券名称。 |
| `price` | `float \| None` | 最新价，元/股。 |
| `price_change` | `float \| None` | 价格涨跌额，元/股。 |
| `change_percent` | `float \| None` | 涨跌幅，%。 |
| `turnover_rate` | `float \| None` | 换手率，%。 |
| `amount` | `float \| None` | 成交额，元。 |
| `market_cap` | `float \| None` | 总市值，元。 |
| `float_shares` | `int \| None` | 流通股本，股。 |
| `total_shares` | `int \| None` | 总股本，股。 |
| `limit_up_time` | `str \| None` | 来源封板时刻，保留来源精度（HH:MM 或 HH:MM:SS）。 |
| `consecutive_limit_up_days` | `int \| None` | 来源当前连板天数。 |
| `is_consecutive_limit_up` | `bool \| None` | 来源是否标记为连板。 |
| `state` | `str \| None` | 来源状态文字。 |
| `previous_consecutive_limit_up_days` | `int \| None` | 来源前一交易日连板天数。 |
| `theme_name` | `str \| None` | 来源题材名称。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.market.consecutive_limit_up()
```

```text
[
  {
    "date": "2026-10-08",
    "code": "600825",
    "exchange": "sh",
    "name": "新华传媒",
    "price": 11.39,
    "price_change": 1.04,
    "change_percent": 10.048,
    "turnover_rate": 0.54,
    "amount": 64324548.0,
    "market_cap": 11901000000.0,
    "float_shares": 1044887872,
    "total_shares": 1044887872,
    "limit_up_time": "09:30",
    "consecutive_limit_up_days": 8,
    "is_consecutive_limit_up": true,
    "state": "8连板",
    "previous_consecutive_limit_up_days": 0,
    "theme_name": "昨日连板"
  },
  ...
]
```

仅返回来源当前连板列表，不提供历史日期查询。

<a id="fund-flow"></a>
## 资金流

<a id="api-fund_flow-stock"></a>
### `fx.fund_flow.stock`

获取单只股票的资金流快照、当日累计资金分时及最近日资金流。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 股票代码；沪市 60/68、深市 00/30 开头。 |
| `days` | `int` | 可选 | `20` | 1 至 50 的正整数，不接受布尔值；仅影响 daily 的最近条数。 |

**返回：`dict`**

顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位股票代码。 |
| `exchange` | `str` | sh 上海、sz 深圳。 |
| `snapshot` | `dict` | 资金流快照。 |
| `intraday` | `list[dict]` | 当日累计资金分时，按时间升序。 |
| `daily` | `list[dict]` | 最近日资金流，按日期升序。 |

snapshot 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日，YYYY-MM-DD。 |
| `main_net_inflow` | `float \| None` | 主力净流入，元。 |
| `main_inflow` | `float \| None` | 主力流入，元。 |
| `main_outflow` | `float \| None` | 主力流出，元。 |
| `main_inflow_percent` | `float \| None` | 主力流入占比，%。 |
| `main_outflow_percent` | `float \| None` | 主力流出占比，%。 |
| `retail_inflow` | `float \| None` | 散户流入，元。 |
| `retail_outflow` | `float \| None` | 散户流出，元。 |
| `retail_inflow_percent` | `float \| None` | 散户流入占比，%。 |
| `retail_outflow_percent` | `float \| None` | 散户流出占比，%。 |
| `super_large_net_inflow` | `float \| None` | 超大单净流入，元。 |
| `large_net_inflow` | `float \| None` | 大单净流入，元。 |
| `medium_net_inflow` | `float \| None` | 中单净流入，元。 |
| `small_net_inflow` | `float \| None` | 小单净流入，元。 |

intraday 每行字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日，YYYY-MM-DD。 |
| `time` | `str` | 来源时刻，HH:MM。 |
| `price` | `float \| None` | 来源价格，元/股。 |
| `cumulative_main_net_inflow` | `float \| None` | 当日累计主力净流入，元。 |
| `cumulative_retail_net_inflow` | `float \| None` | 当日累计散户净流入，元。 |
| `cumulative_super_large_net_inflow` | `float \| None` | 当日累计超大单净流入，元。 |
| `cumulative_large_net_inflow` | `float \| None` | 当日累计大单净流入，元。 |
| `cumulative_medium_net_inflow` | `float \| None` | 当日累计中单净流入，元。 |
| `cumulative_small_net_inflow` | `float \| None` | 当日累计小单净流入，元。 |
| `cumulative_main_inflow` | `float \| None` | 当日累计主力流入，元。 |
| `cumulative_main_outflow` | `float \| None` | 当日累计主力流出，元。 |

daily 每行字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源交易日，YYYY-MM-DD。 |
| `price` | `float \| None` | 该日来源价格，元/股。 |
| `main_net_inflow` | `float \| None` | 该日主力净流入，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.fund_flow.stock(code="600519", days=20)
```

```text
{
  "code": "600519",
  "exchange": "sh",
  "snapshot": {
    "date": "2026-10-08",
    "main_net_inflow": -114334536.0,
    "main_inflow": 1714388884.0,
    "main_outflow": 1828723420.0,
    "main_inflow_percent": 27.0,
    "main_outflow_percent": 29.0,
    "retail_inflow": 1431652168.0,
    "retail_outflow": 1317317632.0,
    "retail_inflow_percent": 23.0,
    "retail_outflow_percent": 21.0,
    "super_large_net_inflow": 414746.0,
    "large_net_inflow": -114749281.0,
    "medium_net_inflow": 114547338.0,
    "small_net_inflow": -212802.0
  },
  "intraday": [
    {
      "date": "2026-10-08",
      "time": "09:30",
      "price": 1246.95,
      "cumulative_main_net_inflow": -17901230.0,
      "cumulative_retail_net_inflow": 17901230.0,
      "cumulative_super_large_net_inflow": -1422536.0,
      "cumulative_large_net_inflow": -16478694.0,
      "cumulative_medium_net_inflow": 17908747.0,
      "cumulative_small_net_inflow": -7517.0,
      "cumulative_main_inflow": 136637961.0,
      "cumulative_main_outflow": 154539191.0
    },
    {
      "date": "2026-10-08",
      "time": "09:31",
      "price": 1244.9,
      "cumulative_main_net_inflow": -19384045.0,
      "cumulative_retail_net_inflow": 19384045.0,
      "cumulative_super_large_net_inflow": 1182570.0,
      "cumulative_large_net_inflow": -20566615.0,
      "cumulative_medium_net_inflow": 19433928.0,
      "cumulative_small_net_inflow": -49883.0,
      "cumulative_main_inflow": 186410433.0,
      "cumulative_main_outflow": 205794479.0
    },
    ...
  ],
  "daily": [
    {
      "date": "2026-09-03",
      "price": 1298.88,
      "main_net_inflow": 91922449.0
    },
    {
      "date": "2026-09-04",
      "price": 1330.0,
      "main_net_inflow": 354120188.0
    },
    ...
  ]
}
```

净流入允许为负。分时资金值为当日累计，不是单分钟净额。daily 的价格采用来源值，当前交易日可能尚未收盘；可用历史不足 days 时返回实际条数，不补数据。

<a id="api-fund_flow-dragon_tiger_list"></a>
### `fx.fund_flow.dragon_tiger_list`

获取指定日期来源提供的全部龙虎榜事件，保留同一证券的不同上榜记录，按代码、交易所和事件标识升序返回。

来源：[爱股票龙虎榜](https://stock.aigupiao.com/pcv/quote/list/type/dragon)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `date` | `str` | 必需 | — | 日期与时刻字符串，格式见[通用约定](#common-conventions)，精确查询对应日期。 |

**返回：`list[dict]`，每行固定十三个字段**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位 ASCII 证券代码。 |
| `exchange` | `str` | 交易所，`sh`、`sz` 或 `bj`。 |
| `name` | `str` | 证券名称。 |
| `trade_id` | `str` | 来源事件标识，用于详情查询。 |
| `close_price` | `float \| None` | 收盘价，元/股。 |
| `change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `amount` | `float \| None` | 该事件统计区间的成交额，元。 |
| `total_buy` | `float \| None` | 合计买入额，元。 |
| `total_net` | `float \| None` | 合计净买入额，元，可负。 |
| `explanation` | `str` | 上榜原因原文。 |
| `period_label` | `str \| None` | 来源区间标记，如 `3日`、`10日`；无标记为 `None`。 |
| `theme_id` | `int \| None` | 来源题材标识。 |
| `theme_name` | `str \| None` | 来源题材名称。 |

**调用与返回示例**

```python
fx.fund_flow.dragon_tiger_list(date="2026-09-30")
```

```text
[
  ...,
  {
    "code": "301139",
    "exchange": "sz",
    "name": "元道退",
    "close_price": 0.91,
    "change_percent": -72.5076,
    "amount": 28660561.0,
    "total_buy": 5016932.0,
    "total_net": 2996129.0,
    "explanation": "退市整理期",
    "trade_id": "100420668",
    "period_label": null,
    "theme_id": 270,
    "theme_name": "储能"
  },
  ...,
  {
    "code": "688137",
    "exchange": "sh",
    "name": "近岸蛋白",
    "close_price": 160.39,
    "change_percent": 13.4701,
    "amount": 11697284100.0,
    "total_buy": 11697284100.0,
    "total_net": -100.0,
    "explanation": "有价格涨跌幅限制的连续10个交易日内收盘价格涨幅偏离值累计达到100%的证券",
    "trade_id": "100421554",
    "period_label": "10日",
    "theme_id": 681,
    "theme_name": "创新药"
  },
  ...
]
```

**必要限制**

只查询指定日期，来源确认当日无榜时返回 `[]`，不寻找上一有榜日期。同股不同 `trade_id` 分别保留；列表保留来源明确身份的合法证券，不过滤退市整理股票、B 股、ETF 或北交所证券。

金额按事件统计区间读取，累计事件的成交额不等同当日成交额。只覆盖来源提供的记录，不保证覆盖交易所全部龙虎榜。

<a id="api-fund_flow-dragon_tiger_detail"></a>
### `fx.fund_flow.dragon_tiger_detail`

获取一个龙虎榜事件的成交摘要及买卖营业部席位，席位保持来源顺序。

来源：[爱股票龙虎榜](https://stock.aigupiao.com/pcv/quote/list/type/dragon)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 列表中的六位 ASCII 证券代码，当前支持沪市 60/68、深市 00/30 开头的股票。 |
| `date` | `str` | 必需 | — | 同一事件查询日期，字符串格式见[通用约定](#common-conventions)。 |
| `trade_id` | `str` | 必需 | — | 同条列表记录的非空 ASCII 数字字符串事件标识。 |

**返回：`dict`，固定十二个顶层字段**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 来源确认的证券代码。 |
| `exchange` | `str` | 来源确认的交易所。 |
| `name` | `str` | 证券名称。 |
| `close_price` | `float \| None` | 收盘价，元/股。 |
| `change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `amount` | `float \| None` | 该事件统计区间的成交额，元。 |
| `total_buy` | `float \| None` | 合计买入额，元。 |
| `total_sell` | `float \| None` | 合计卖出额，元。 |
| `total_net` | `float \| None` | 合计净买入额，元，可负。 |
| `explanation` | `str` | 上榜原因原文。 |
| `buy_seats` | `list[dict]` | 来源买入榜席位。 |
| `sell_seats` | `list[dict]` | 来源卖出榜席位。 |

`buy_seats`、`sell_seats` 每行固定五个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `seat_name` | `str` | 营业部名称。 |
| `seat_code` | `str \| None` | 来源营业部身份代码。 |
| `buy_amount` | `float \| None` | 买入额，元。 |
| `sell_amount` | `float \| None` | 卖出额，元。 |
| `net_amount` | `float \| None` | 净买入额，元，可负。 |

**调用与返回示例**

```python
fx.fund_flow.dragon_tiger_detail(
    code="301139", date="2026-09-30", trade_id="100420668"
)
```

```text
{
  "code": "301139",
  "exchange": "sz",
  "name": "元道退",
  "close_price": 0.91,
  "change_percent": -72.5076,
  "amount": 28660561.0,
  "total_buy": 5016932.0,
  "total_net": 2996129.0,
  "explanation": "退市整理期",
  "total_sell": 2020803.0,
  "buy_seats": [
    {
      "seat_name": "国泰海通证券股份有限公司成都龙腾东路营业部",
      "seat_code": "10564259",
      "buy_amount": 1365120.0,
      "sell_amount": 237.0,
      "net_amount": 1364883.0
    },
    ...
  ],
  "sell_seats": [
    {
      "seat_name": "麦高证券有限责任公司沈阳建设西路证券营业部",
      "seat_code": "10065379",
      "buy_amount": 0.0,
      "sell_amount": 459805.0,
      "net_amount": -459805.0
    },
    ...
  ]
}
```

**必要限制**

三个参数须来自同一事件。详情仅支持沪市 60/68、深市 00/30 开头的股票，支持范围小于列表。

只返回该事件来源提供的买卖榜，不代表全部交易席位，不另取营业部历史、行情或评论。同一营业部同时出现在买卖两榜时分别保留。

<a id="sector-data"></a>
## 板块

<a id="api-sector-tx_sectors"></a>
### `fx.sector.tx_sectors`

获取股票所属地域、行业和概念板块。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 股票代码；沪市 60/68、深市 00/30 开头，指数不适用。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sector_type` | `str` | area 地域、industry 行业、concept 概念。 |
| `sector_code` | `str` | 来源板块代码。 |
| `sector_name` | `str \| None` | 板块名称。 |
| `change_percent` | `float \| None` | 板块涨跌幅，%。 |
| `level` | `int \| None` | 来源板块层级。 |
| `tag` | `str \| None` | 来源板块标签。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.tx_sectors(code="600519")
```

```text
[
  {
    "sector_type": "area",
    "sector_code": "03001173",
    "sector_name": "贵州",
    "change_percent": -0.02,
    "level": null,
    "tag": null
  },
  {
    "sector_type": "industry",
    "sector_code": "01801120",
    "sector_name": "食品饮料",
    "change_percent": -0.03,
    "level": 1,
    "tag": null
  },
  ...
]
```

按地域、行业、概念分类，再按板块代码升序；保留来源提供的全部有效板块。

<a id="api-sector-em_keywords"></a>
### `fx.sector.em_keywords`

获取股票的热门概念及来源命中次数。

来源：东方财富。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 股票代码；沪市 60/68、深市 00/30 开头，指数不适用。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `keyword_code` | `str` | 来源概念代码，BK加四位数字。 |
| `keyword_name` | `str \| None` | 热门概念名称。 |
| `hit_count` | `int \| None` | 来源命中次数。 |
| `calculated_at` | `str \| None` | 来源统计时刻，ISO 格式，带 +08:00 时区。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.em_keywords(code="600519")
```

```text
[
  {
    "keyword_code": "BK0896",
    "keyword_name": "白酒",
    "hit_count": 4536,
    "calculated_at": "2026-10-08T16:00:00+08:00"
  },
  {
    "keyword_code": "BK0999",
    "keyword_name": "茅指数",
    "hit_count": 201,
    "calculated_at": "2026-10-08T16:00:00+08:00"
  },
  ...
]
```

返回来源当前热门概念，保持来源顺序；命中次数按来源定义。

<a id="api-sector-tx_industry_comparison"></a>
### `fx.sector.tx_industry_comparison`

获取股票与所属行业及来源市场均值的对比。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 股票代码；沪市 60/68、深市 00/30 开头，指数不适用。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位股票代码。 |
| `exchange` | `str` | sh 上海、sz 深圳。 |
| `industry_code` | `str` | 来源行业代码。 |
| `industry_name` | `str \| None` | 行业名称。 |
| `pe` | `float \| None` | 市盈率，倍。 |
| `eps` | `float \| None` | 每股收益，元/股。 |
| `float_market_cap` | `float \| None` | 来源流通 A 股市值，元。 |
| `pe_rank` | `int \| None` | 来源行业市盈率排名。 |
| `eps_rank` | `int \| None` | 来源行业每股收益排名。 |
| `float_market_cap_rank` | `int \| None` | 来源行业流通A股市值排名。 |
| `industry_count` | `int \| None` | 来源行业样本数。 |
| `industry_avg_pe` | `float \| None` | 行业平均市盈率，倍。 |
| `industry_avg_eps` | `float \| None` | 行业平均每股收益，元/股。 |
| `industry_avg_float_market_cap` | `float \| None` | 行业平均流通 A 股市值，元。 |
| `market_avg_pe` | `float \| None` | 来源市场平均市盈率，倍。 |
| `market_avg_eps` | `float \| None` | 来源市场平均每股收益，元/股。 |
| `market_avg_float_market_cap` | `float \| None` | 来源市场平均流通 A 股市值，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.tx_industry_comparison(code="600519")
```

```json
{
  "code": "600519",
  "exchange": "sh",
  "industry_code": "012010",
  "industry_name": "酿酒",
  "pe": 49.91,
  "eps": 17.99,
  "float_market_cap": 2188925000000.0,
  "pe_rank": 23,
  "eps_rank": 1,
  "float_market_cap_rank": 1,
  "industry_count": 35,
  "industry_avg_pe": 54.644,
  "industry_avg_eps": 2.244,
  "industry_avg_float_market_cap": 71796400000.0,
  "market_avg_pe": 52.12,
  "market_avg_eps": 0.263,
  "market_avg_float_market_cap": 30982999999.999996
}
```

市场均值按来源对应的沪市或深市口径。市盈率和每股收益可为负；来源未标明市盈率是否为 TTM、每股收益报告期或排名方向。

<a id="api-sector-ths_concept_list"></a>
### `fx.sector.ths_concept_list`

获取同花顺提供的概念目录。

来源：同花顺。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 同花顺概念目录代码。 |
| `name` | `str` | 概念名称。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.ths_concept_list()
```

```text
[
  {
    "code": "300008",
    "name": "新能源汽车"
  },
  {
    "code": "300013",
    "name": "大飞机"
  },
  {
    "code": "300018",
    "name": "参股保险"
  },
  ...
]
```

按代码升序返回当前目录页面提供的概念；名称可能重复，查询行情时使用 code。

<a id="api-sector-ths_concept_quote_snapshot"></a>
### `fx.sector.ths_concept_quote_snapshot`

获取同花顺概念指数的行情快照。

来源：同花顺。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 数字字符串；取自 `ths_concept_list` 返回的同花顺概念目录代码，如 `"302035"`。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 同花顺概念目录代码。 |
| `name` | `str` | 概念名称。 |
| `date` | `str \| None` | 来源行情日期，YYYY-MM-DD。 |
| `time` | `str \| None` | 来源行情时刻，北京时间，保留 HH:MM 或 HH:MM:SS 精度。 |
| `index_level` | `float \| None` | 指数点位。 |
| `previous_close` | `float \| None` | 昨收点位。 |
| `open` | `float \| None` | 开盘点位。 |
| `high` | `float \| None` | 最高点位。 |
| `low` | `float \| None` | 最低点位。 |
| `level_change` | `float \| None` | 点位变化。 |
| `change_percent` | `float \| None` | 涨跌幅，%。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元。 |
| `net_inflow` | `float \| None` | 资金净流入，元。 |
| `up_count` | `int \| None` | 上涨股票数量。 |
| `down_count` | `int \| None` | 下跌股票数量。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.ths_concept_quote_snapshot(code="302035")
```

```json
{
  "code": "302035",
  "name": "人工智能",
  "date": "2026-10-08",
  "time": "15:00",
  "index_level": 1250.956,
  "previous_close": 1273.197,
  "open": 1274.838,
  "high": 1282.946,
  "low": 1243.436,
  "level_change": -22.241,
  "change_percent": -1.75,
  "volume": 19950267000,
  "amount": 318787330000.0,
  "net_inflow": -24831000000.0,
  "up_count": 205,
  "down_count": 863
}
```

来源行情时间缺失时返回 None，存在但无效时明确报错。

<a id="api-sector-ths_concept_ohlcv"></a>
### `fx.sector.ths_concept_ohlcv`

获取日期范围内的同花顺概念指数日线，包含首尾日期。

来源：同花顺。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 数字字符串；取自 `ths_concept_list` 返回的同花顺概念目录代码，如 `"302035"`。 |
| `start_date` | `str \| datetime.date` | 必需 | — | 开始日期，包含当日；接受 `datetime.date` 或[通用约定](#common-conventions)中的日期与时刻字符串。 |
| `end_date` | `str \| datetime.date` | 必需 | — | 结束日期，包含当日；类型及格式同上，不得早于 `start_date`。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源日线日期，YYYY-MM-DD。 |
| `open` | `float \| None` | 开盘点位。 |
| `high` | `float \| None` | 最高点位。 |
| `low` | `float \| None` | 最低点位。 |
| `close` | `float \| None` | 收盘点位。 |
| `volume` | `int \| None` | 成交量，股。 |
| `amount` | `float \| None` | 成交额，元。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.sector.ths_concept_ohlcv(
    code="302035",
    start_date="2026-09-29",
    end_date="2026-09-30",
)
```

```json
[
  {
    "date": "2026-09-29",
    "open": 1261.624,
    "high": 1285.105,
    "low": 1261.167,
    "close": 1278.405,
    "volume": 18665594000,
    "amount": 281681560000.0
  },
  {
    "date": "2026-09-30",
    "open": 1283.44,
    "high": 1283.624,
    "low": 1270.619,
    "close": 1273.197,
    "volume": 18118957000,
    "amount": 287163320000.0
  }
]
```

来源日线可能晚于快照更新；仅返回来源提供的日期，不补数据。

<a id="company-data"></a>
## 上市公司信息

<a id="api-company-info"></a>
### `fx.company.info`

获取公司简介、股本股东摘要、高管、分红、回购，以及财务摘要、主营收入分布和行业财务对比。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 字符串股票代码，支持沪市 60/68、深市 00/30 开头的股票。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位股票代码。 |
| `exchange` | `str` | 交易所，sh 或 sz。 |
| `profile` | `dict` | 公司简介。 |
| `executives` | `list[dict]` | 来源提供的高管记录。 |
| `executive_share_changes` | `list[dict]` | 高管持股变动记录。 |
| `share_capital` | `dict` | 股本摘要。 |
| `shareholder_summary` | `dict` | 股东摘要。 |
| `dividends` | `list[dict]` | 分红配股记录。 |
| `repurchases` | `list[dict]` | 回购记录。 |
| `financial_summary` | `dict` | 当前及历史财务摘要。 |
| `revenue_breakdown` | `list[dict]` | 按期间和维度分组的主营收入。 |
| `industry_comparison` | `dict` | 五项核心财务指标的行业对比。 |

**简介及记录**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `profile.company_name` | `str \| None` | 公司名称。 |
| `profile.business_description` | `str \| None` | 主营业务描述。 |
| `profile.issue_price` | `float \| None` | 发行价，人民币元/股。 |
| `profile.listing_date` | `str \| None` | 上市日期，YYYY-MM-DD。 |
| `executives[].name` | `str` | 姓名。 |
| `executives[].roles` | `list[str] \| None` | 职务。 |
| `executives[].shares` | `int \| None` | 持股数量，股。 |
| `executives[].compensation` | `float \| None` | 来源薪酬，人民币元。 |
| `executive_share_changes[].announcement_date` | `str \| None` | 公告日期，YYYY-MM-DD。 |
| `executive_share_changes[].person_name` | `str \| None` | 姓名。 |
| `executive_share_changes[].share_change` | `int \| None` | 持股变动，股；可为负。 |
| `executive_share_changes[].average_price` | `float \| None` | 变动均价，人民币元/股。 |
| `share_capital.total_shares` | `int \| None` | 总股本，股。 |
| `share_capital.float_shares` | `int \| None` | 流通股本，股。 |
| `shareholder_summary.shareholder_count` | `int \| None` | 股东人数，户。 |
| `shareholder_summary.average_shares_per_holder` | `float \| None` | 户均持股，股。 |
| `shareholder_summary.shareholder_count_change_percent` | `float \| None` | 股东人数环比，%。 |
| `shareholder_summary.top10_holder_percent` | `float \| None` | 前十股东持股比例，%。 |
| `shareholder_summary.top10_float_holder_percent` | `float \| None` | 前十流通股东持股比例，%。 |
| `dividends[].period` | `str \| None` | 来源期间原文。 |
| `dividends[].announcement_date` | `str \| None` | 公告日期，YYYY-MM-DD。 |
| `dividends[].stock_dividend_per_10` | `float \| None` | 每 10 股送股数量，股。 |
| `dividends[].capitalization_per_10` | `float \| None` | 每 10 股转增数量，股。 |
| `dividends[].cash_dividend_per_10` | `float \| None` | 每 10 股派现金额，人民币元。 |
| `dividends[].rights_issue_per_10` | `float \| None` | 每 10 股配股数量，股。 |
| `dividends[].record_date` | `str \| None` | 股权登记日，YYYY-MM-DD。 |
| `dividends[].ex_date` | `str \| None` | 除权除息日，YYYY-MM-DD。 |
| `dividends[].description` | `str \| None` | 来源分配方案。 |
| `repurchases[].date` | `str \| None` | 来源回购记录日期，YYYY-MM-DD。 |
| `repurchases[].quantity` | `int \| None` | 回购数量，股。 |
| `repurchases[].average_price` | `float \| None` | 回购均价，元/股；币种见 currency。 |
| `repurchases[].currency` | `str \| None` | 来源币种，如 CNY、HKD。 |
| `repurchases[].fund_amount` | `float \| None` | 回购金额，元；币种见 currency。 |
| `repurchases[].market` | `str \| None` | 来源市场。 |

**财务摘要**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `financial_summary.current` | `dict` | 来源当前财务摘要。 |
| `financial_summary.current.period` | `str` | 来源报告期标签，如 2026中报。 |
| `financial_summary.current.eps` | `float \| None` | 每股收益，人民币元/股。 |
| `financial_summary.current.revenue` | `float \| None` | 来源营业收入，人民币元。 |
| `financial_summary.current.revenue_change_percent` | `float \| None` | 营业收入同比，%。 |
| `financial_summary.current.net_profit` | `float \| None` | 来源净利润，人民币元。 |
| `financial_summary.current.net_profit_change_percent` | `float \| None` | 净利润同比，%。 |
| `financial_summary.current.book_value_per_share` | `float \| None` | 每股净资产，人民币元/股。 |
| `financial_summary.current.net_assets` | `float \| None` | 净资产，人民币元。 |
| `financial_summary.current.goodwill` | `float \| None` | 商誉，人民币元。 |
| `financial_summary.current.goodwill_to_net_assets_percent` | `float \| None` | 商誉占净资产比例，%。 |
| `financial_summary.current.roe_percent` | `float \| None` | 净资产收益率，%。 |
| `financial_summary.current.debt_ratio_percent` | `float \| None` | 资产负债率，%。 |
| `financial_summary.current.pe_ttm` | `float \| None` | 市盈率 TTM，倍。 |
| `financial_summary.current.pb` | `float \| None` | 市净率，倍。 |
| `financial_summary.history` | `list[dict]` | 来源历史财务摘要。 |
| `financial_summary.history[].period` | `str` | 来源年度标签，如 2025。 |
| `financial_summary.history[].eps` | `float \| None` | 每股收益，人民币元/股。 |
| `financial_summary.history[].revenue` | `float \| None` | 来源营业收入，人民币元。 |
| `financial_summary.history[].revenue_change_percent` | `float \| None` | 营业收入同比，%。 |
| `financial_summary.history[].net_profit` | `float \| None` | 来源净利润，人民币元。 |
| `financial_summary.history[].net_profit_change_percent` | `float \| None` | 净利润同比，%。 |
| `financial_summary.history[].eps_change_percent` | `float \| None` | 每股收益同比，%。 |

**主营收入分布**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `revenue_breakdown[].period` | `str` | 来源报告期标签。 |
| `revenue_breakdown[].dimension` | `str` | industry 行业、product 产品、region 地区。 |
| `revenue_breakdown[].items` | `list[dict]` | 来源主要项目，保留“其他收入之和”等汇总行。 |
| `revenue_breakdown[].other_items` | `list[dict]` | 来源另列的其他项目。 |
| `revenue_breakdown[].items[].name` | `str` | 项目名称。 |
| `revenue_breakdown[].items[].unit` | `str \| None` | 来源金额单位。 |
| `revenue_breakdown[].items[].revenue` | `float \| None` | 收入，统一为人民币元。 |
| `revenue_breakdown[].items[].revenue_share_percent` | `float \| None` | 收入占比，%。 |
| `revenue_breakdown[].other_items[].name` | `str` | 项目名称。 |
| `revenue_breakdown[].other_items[].unit` | `str \| None` | 来源金额单位。 |
| `revenue_breakdown[].other_items[].revenue` | `float \| None` | 收入，统一为人民币元。 |
| `revenue_breakdown[].other_items[].revenue_share_percent` | `float \| None` | 收入占比，%。 |

**行业财务对比**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `industry_comparison.period` | `str` | 来源报告期标签。 |
| `industry_comparison.period_end` | `str \| None` | 来源报告期末，YYYY-MM-DD。 |
| `industry_comparison.industry_name` | `str \| None` | 来源行业名称。 |
| `industry_comparison.metrics` | `list[dict]` | 每股收益、收入、净利润、每股净资产、净资产收益率五项指标。 |
| `industry_comparison.metrics[].metric` | `str` | eps、revenue、net_profit、book_value_per_share、roe_percent。 |
| `industry_comparison.metrics[].unit` | `str` | 元/股、元或 %。 |
| `industry_comparison.metrics[].company_value` | `float \| None` | 公司值。 |
| `industry_comparison.metrics[].industry_average` | `float \| None` | 来源行业平均值。 |
| `industry_comparison.metrics[].industry_max` | `float \| None` | 来源行业最大值。 |
| `industry_comparison.metrics[].industry_min` | `float \| None` | 来源行业最小值。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.company.info(code="600519")
```

```text
{
  "code": "600519",
  "exchange": "sh",
  "profile": {
    "company_name": "贵州茅台酒股份有限公司",
    "business_description": "贵州茅台酒系列产品的生产与销售,饮料、食品、包装材料的生产与销售,防伪技术开发;信息产业相关产品的研制和开发等。",
    "issue_price": 31.39,
    "listing_date": "2001-08-27"
  },
  "executives": [
    {
      "name": "陈华",
      "roles": ["党委书记", "董事长", "董事"],
      "shares": null,
      "compensation": null
    },
    {
      "name": "余思明",
      "roles": ["董事会秘书", "党委委员", "财务总监"],
      "shares": null,
      "compensation": null
    },
    ...
  ],
  "executive_share_changes": [
    {
      "announcement_date": "2018-09-26",
      "person_name": "万波",
      "share_change": -700,
      "average_price": 725.92
    },
    {
      "announcement_date": "2018-01-03",
      "person_name": "万波",
      "share_change": 700,
      "average_price": 689.0
    }
  ],
  "share_capital": {
    "total_shares": 1250081601,
    "float_shares": 1250000000
  },
  "shareholder_summary": {
    "shareholder_count": 296400,
    "average_shares_per_holder": 4217.49,
    "shareholder_count_change_percent": 21.9,
    "top10_holder_percent": 67.62,
    "top10_float_holder_percent": 67.62
  },
  "dividends": [
    {
      "period": "2026",
      "announcement_date": "2026-08-15",
      "stock_dividend_per_10": 0.0,
      "capitalization_per_10": 0.0,
      "cash_dividend_per_10": 0.0,
      "rights_issue_per_10": 0.0,
      "record_date": null,
      "ex_date": null,
      "description": "不分配不转增"
    },
    {
      "period": "2025",
      "announcement_date": "2026-06-22",
      "stock_dividend_per_10": 0.0,
      "capitalization_per_10": 0.0,
      "cash_dividend_per_10": 280.242,
      "rights_issue_per_10": 0.0,
      "record_date": "2026-06-25",
      "ex_date": "2026-06-26",
      "description": "10派280.242元"
    },
    ...
  ],
  "repurchases": [
    {
      "date": "2026-05-27",
      "quantity": 1105300,
      "average_price": 1338.1,
      "currency": "CNY",
      "fund_amount": 1479000000.0,
      "market": null
    },
    {
      "date": "2026-04-30",
      "quantity": 289100,
      "average_price": 1413.9,
      "currency": "CNY",
      "fund_amount": 409000000.0,
      "market": null
    },
    ...
  ],
  "financial_summary": {
    "current": {
      "period": "2026中报",
      "eps": 35.57,
      "revenue": 92278000000.0,
      "revenue_change_percent": 1.3,
      "net_profit": 44517000000.0,
      "net_profit_change_percent": -1.95,
      "book_value_per_share": 200.99,
      "net_assets": 251254000000.0,
      "goodwill": null,
      "goodwill_to_net_assets_percent": null,
      "roe_percent": 16.75,
      "debt_ratio_percent": 15.19,
      "pe_ttm": 19.28,
      "pb": 6.25
    },
    "history": [
      {
        "period": "2025",
        "revenue": 172054000000.0,
        "revenue_change_percent": -1.2,
        "net_profit": 82320000000.0,
        "net_profit_change_percent": -4.53,
        "eps": 65.66,
        "eps_change_percent": -4.34
      },
      {
        "period": "2024",
        "revenue": 174144000000.0,
        "revenue_change_percent": 15.66,
        "net_profit": 86228000000.0,
        "net_profit_change_percent": 15.38,
        "eps": 68.64,
        "eps_change_percent": 15.38
      },
      ...
    ]
  },
  "revenue_breakdown": [
    {
      "period": "2026中报",
      "dimension": "region",
      "items": [
        {
          "name": "国内",
          "unit": "元",
          "revenue": 89666000000.0,
          "revenue_share_percent": 98.86
        },
        {
          "name": "国外",
          "unit": "元",
          "revenue": 1037000000.0,
          "revenue_share_percent": 1.14
        }
      ],
      "other_items": []
    },
    {
      "period": "2026中报",
      "dimension": "product",
      "items": [
        {
          "name": "茅台酒",
          "unit": "元",
          "revenue": 77724000000.0,
          "revenue_share_percent": 85.69
        },
        {
          "name": "其他系列酒",
          "unit": "元",
          "revenue": 12934000000.0,
          "revenue_share_percent": 14.26
        },
        ...
      ],
      "other_items": []
    },
    ...
  ],
  "industry_comparison": {
    "period": "2026中报",
    "period_end": "2026-06-30",
    "industry_name": "白酒Ⅱ",
    "metrics": [
      {
        "metric": "eps",
        "unit": "元/股",
        "company_value": 35.57,
        "industry_average": 2.9911,
        "industry_max": 35.57,
        "industry_min": -0.1
      },
      {
        "metric": "revenue",
        "unit": "元",
        "company_value": 92278072083.21,
        "industry_average": 10415473737.34,
        "industry_max": 92278072083.21,
        "industry_min": 48505147.53
      },
      ...
    ]
  }
}
```

仅返回来源摘要及近期记录，不保证全部高管或历史。财务报告期保留来源标签；不同业务块的数值按各自来源精度保留，不互相补值。行业对比仅含表列五项指标；未提供日期的摘要不补报告期。回购均价和金额按各条 currency 币种返回。

<a id="api-company-float_shareholders"></a>
### `fx.company.float_shareholders`

获取最近报告期或指定年份的流通股东记录。

来源：腾讯财经。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 字符串股票代码，支持沪市 60/68、深市 00/30 开头的股票。 |
| `year` | `int \| None` | 可选 | `None` | 非布尔的四位整数；None 返回来源最近最多四个报告期，指定年份仅返回来源支持的实际报告期。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `period_end` | `str` | 报告期末，YYYY-MM-DD。 |
| `holder_name` | `str` | 股东名称。 |
| `shares` | `int \| None` | 持股数量，股。 |
| `share_type` | `str \| None` | 来源股份性质。 |
| `holding_percent` | `float \| None` | 来源持有比例，%。 |
| `previous_shares` | `int \| None` | 上期持股数量，股。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.company.float_shareholders(code="600519")
```

```text
[
  {
    "period_end": "2026-06-30",
    "holder_name": "中国贵州茅台酒厂(集团)有限责任公司",
    "shares": 681283000,
    "share_type": "国有股",
    "holding_percent": 54.4991,
    "previous_shares": 681283000
  },
  {
    "period_end": "2026-06-30",
    "holder_name": "贵州省国有资本运营有限责任公司",
    "shares": 56996800,
    "share_type": "国有股",
    "holding_percent": 4.55944,
    "previous_shares": 56996800
  },
  ...
]
```

```python
fx.company.float_shareholders(code="000333", year=2013)
```

```text
[
  {
    "period_end": "2013-12-31",
    "holder_name": "全国社保基金一零四组合",
    "shares": 21688900,
    "share_type": "境内法人股",
    "holding_percent": 1.28616,
    "previous_shares": 21333300
  },
  {
    "period_end": "2013-12-31",
    "holder_name": "宁波开联实业发展有限公司",
    "shares": 19380700,
    "share_type": "境内法人股",
    "holding_percent": 1.14929,
    "previous_shares": 19380700
  },
  ...
]
```

按报告期倒序排列，同期保留来源顺序。持有比例按来源定义；不补报告期，也不承诺全部历史，不支持的年份抛出 ValueError。

<a id="financial-data"></a>
## 财务

<a id="api-financial-statements"></a>
### `fx.financial.statements`

获取股票的一种财务报表，按报告期降序返回来源业务科目。

来源：同花顺。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 字符串股票代码，支持沪市 60/68、深市 00/30 开头的股票。 |
| `statement` | `str` | 必需 | — | `"balance_sheet"` 资产负债表、`"income_statement"` 利润表、`"cash_flow_statement"` 现金流量表。 |
| `period_end` | `str \| None` | 可选 | `None` | 精确报告期末，字符串格式见[通用约定](#common-conventions)；None 返回来源实际报告期，指定日期不存在时抛出 ValueError。 |
| `max_periods` | `int \| None` | 可选 | `None` | 非布尔正整数，截取最近若干期；None 不限数量。可与 period_end 同用，精确日期最多返回一期。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `period_end` | `str` | 来源报告期末，YYYY-MM-DD。 |
| `items` | `list[dict]` | 该期业务科目，保持来源顺序。 |
| `items[].name` | `str` | 来源完整科目名称。 |
| `items[].unit` | `str \| None` | 已知金额单位统一为元；来源未提供单位时为 None。 |
| `items[].value` | `float \| None` | 科目数值，按已知单位转换，保留来源显示精度。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.financial.statements(
    code="600519",
    statement="income_statement",
    period_end="2026-06-30",
    max_periods=1,
)
```

```text
[
  {
    "period_end": "2026-06-30",
    "items": [
      {
        "name": "一、营业总收入",
        "unit": "元",
        "value": 92278000000.0
      },
      {
        "name": "其中：营业收入",
        "unit": "元",
        "value": 90703000000.0
      },
      ...
    ]
  }
]
```

仅返回来源实际报告期与科目，不承诺全部历史；基本与稀释每股收益、集团与归母利润分别保留，不合并科目。

<a id="regulation-data"></a>
## 监管

<a id="api-regulation-watchlist"></a>
### `fx.regulation.watchlist`

获取东方财富整理的重点监控证券名单。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str` | 证券简称。 |
| `monitor_start_date` | `str \| None` | 来源监控开始日期，YYYY-MM-DD。 |
| `expected_end_date` | `str \| None` | 来源预计截止日期，YYYY-MM-DD。 |
| `source_url` | `str \| None` | 来源附带的说明链接。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.regulation.watchlist()
```

```text
[
  {
    "code": "501225",
    "exchange": "sh",
    "name": "全球芯片",
    "monitor_start_date": "2026-10-09",
    "expected_end_date": "2026-10-22",
    "source_url": "https://wap.18.cn/app/detail/818/3314"
  },
  {
    "code": "920575",
    "exchange": "bj",
    "name": "*ST康乐",
    "monitor_start_date": "2026-10-08",
    "expected_end_date": "2026-10-09",
    "source_url": null
  },
  ...
]
```

保留来源证券，包括股票与 ETF。预计截止日期为来源预计值，说明链接不一定是交易所公告；名单不保证覆盖全部监管证券。

<a id="api-regulation-abnormal_records"></a>
### `fx.regulation.abnormal_records`

获取普通或严重异常波动公告记录。

来源：东方财富。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `event_type` | `str` | 可选 | `"ordinary"` | `"ordinary"` 普通异常波动、`"severe"` 严重异常波动。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str` | 证券简称。 |
| `event_type` | `str` | ordinary 普通、severe 严重。 |
| `start_date` | `str \| None` | 来源异动开始日期。 |
| `end_date` | `str \| None` | 来源异动截止日期。 |
| `announcement_date` | `str` | 公告日期，YYYY-MM-DD。 |
| `announcement_id` | `str` | 来源公告标识。 |
| `reason` | `str \| None` | 具体异动说明。 |
| `reason_type` | `str \| None` | 来源归类的异动原因。 |
| `monitor_start_date` | `str \| None` | 监控开始日期；普通记录为 None。 |
| `monitor_end_date` | `str \| None` | 监控结束日期；普通记录为 None。 |
| `monitor_status` | `str \| None` | current 当前、history 历史；普通记录为 None。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.regulation.abnormal_records(event_type="severe")
```

```text
[
  {
    "code": "688137",
    "exchange": "sh",
    "name": "近岸蛋白",
    "event_type": "severe",
    "start_date": "2026-09-16",
    "end_date": "2026-09-30",
    "announcement_date": "2026-10-08",
    "announcement_id": "AN202610071830184946",
    "reason": "公司股票于2026年9月28日、9月29日、9月30日连续3个交易日内日收盘价格涨幅偏离值累计超过30%;公司股票交易于2026年9月16日至2026年9月30日连续10个交易日内收盘价累计涨幅偏离值达到100%的异常波动情形",
    "reason_type": "连续10个交易日内日收盘价格涨幅偏离值累计达到100%",
    "monitor_start_date": "2026-10-08",
    "monitor_end_date": "2026-10-21",
    "monitor_status": "current"
  },
  {
    "code": "920229",
    "exchange": "bj",
    "name": "世纪数码",
    "event_type": "severe",
    "start_date": "2026-09-23",
    "end_date": "2026-09-29",
    "announcement_date": "2026-09-29",
    "announcement_id": "AN202609291830000566",
    "reason": "公司股票连续4个交易日(2026年9月23日至2026年9月29日)内日收盘价跌幅偏离值累计达到-61.39%,根据《北京证券交易所交易规则》的有关规定,属于股票交易严重异常波动情形",
    "reason_type": "连续10个交易日内日收盘价跌幅偏离值累计达到60%",
    "monitor_start_date": "2026-09-30",
    "monitor_end_date": "2026-10-20",
    "monitor_status": "current"
  },
  ...
]
```

保留所选类型的全部来源记录，严重异动包括当前及历史记录。日期和历史范围以来源为准，不以公告日期补事件日期。

<a id="api-regulation-abnormal_prediction_history"></a>
### `fx.regulation.abnormal_prediction_history`

获取严重异动预测历史及来源标明的当前记录。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str` | 证券简称。 |
| `date` | `str` | 来源预测交易日期，YYYY-MM-DD。 |
| `change_percent` | `float \| None` | 当日涨跌幅，%。 |
| `window_days` | `int \| None` | 来源已统计区间天数。 |
| `deviation_percent` | `float \| None` | 来源区间偏离值，%。 |
| `trigger_change_percent` | `float \| None` | 来源预测触发收盘涨跌幅，%。 |
| `is_triggered` | `bool \| None` | 来源模型判断是否发生。 |
| `rule` | `str` | 来源规则描述。 |
| `direction` | `str \| None` | up 上行、down 下行。 |
| `is_current` | `bool \| None` | 来源标明是否为当前预测记录。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.regulation.abnormal_prediction_history()
```

```text
[
  {
    "code": "301190",
    "exchange": "sz",
    "name": "善水科技",
    "date": "2026-10-08",
    "change_percent": 9.991650431394,
    "window_days": 6,
    "deviation_percent": 102.08,
    "trigger_change_percent": 8.81,
    "is_triggered": true,
    "rule": "连续十个交易日内日收盘价涨跌幅偏离值累计达到+100%",
    "direction": "up",
    "is_current": true
  },
  {
    "code": "301560",
    "exchange": "sz",
    "name": "众捷股份",
    "date": "2026-10-08",
    "change_percent": 1.08293713682,
    "window_days": 10,
    "deviation_percent": 75.81,
    "trigger_change_percent": 15.47,
    "is_triggered": false,
    "rule": "连续十个交易日内日收盘价涨跌幅偏离值累计达到+100%",
    "direction": "up",
    "is_current": true
  },
  ...
]
```

预测属于来源模型结果，不是交易所监管认定；统计天数不必等于规则最大窗口，历史范围以来源实际覆盖为准。

<a id="api-regulation-severe_predictions"></a>
### `fx.regulation.severe_predictions`

获取当前及次一交易日的严重异动预测。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str` | 证券简称。 |
| `date` | `str` | 来源观察交易日期，YYYY-MM-DD。 |
| `board` | `str` | main 主板、chinext 创业板、star 科创板、bse 北交所。 |
| `rule` | `str` | 来源规则描述。 |
| `window_days` | `int \| None` | 来源已统计区间天数。 |
| `deviation_percent` | `float \| None` | 来源区间偏离值，%。 |
| `trigger_change_percent` | `float \| None` | 来源预测触发涨跌幅，%。 |
| `change_percent` | `float \| None` | 观察日涨跌幅，%。 |
| `scenario` | `str` | current 当前、next_session 次一交易日预测。 |
| `is_triggered` | `bool \| None` | 来源当前模型是否触发；次一交易日预测为 None。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.regulation.severe_predictions()
```

```text
[
  {
    "code": "600825",
    "exchange": "sh",
    "name": "新华传媒",
    "date": "2026-10-08",
    "board": "main",
    "rule": "主板连续10个交易日内4次出现同向异常波动",
    "window_days": 1,
    "deviation_percent": 10.84,
    "trigger_change_percent": 8.33,
    "change_percent": 10.05,
    "scenario": "next_session",
    "is_triggered": null
  },
  {
    "code": "688175",
    "exchange": "sh",
    "name": "高凌信息",
    "date": "2026-10-08",
    "board": "star",
    "rule": "连续十个交易日内日收盘价涨跌幅偏离值累计达到+100%",
    "window_days": 9,
    "deviation_percent": 80.09,
    "trigger_change_percent": 11.66,
    "change_percent": 6.73,
    "scenario": "next_session",
    "is_triggered": null
  },
  ...
]
```

同证券同规则的不同场景分别保留。来源模型状态不是交易所认定或停牌结论；次一交易日预测仅提供观察日期，不补目标日期。

<a id="api-regulation-abnormal_counts"></a>
### `fx.regulation.abnormal_counts`

获取来源十日内多次异常波动统计。

来源：东方财富。

**参数**

无。

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位证券代码。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str` | 证券简称。 |
| `date` | `str` | 来源观察交易日期，YYYY-MM-DD。 |
| `price` | `float \| None` | 股价，元/股。 |
| `change_percent` | `float \| None` | 涨跌幅，%。 |
| `abnormal_count` | `int \| None` | 来源十日内异常波动次数。 |
| `max_deviation_percent` | `float \| None` | 来源十日内最大偏离值，%。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX(timeout=20)
fx.regulation.abnormal_counts()
```

```text
[
  {
    "code": "000504",
    "exchange": "sz",
    "name": "南华生物",
    "date": "2026-10-08",
    "price": 11.45,
    "change_percent": -7.81,
    "abnormal_count": 2,
    "max_deviation_percent": 42.94
  },
  {
    "code": "000678",
    "exchange": "sz",
    "name": "襄阳轴承",
    "date": "2026-10-08",
    "price": 12.24,
    "change_percent": -5.04,
    "abnormal_count": 2,
    "max_deviation_percent": 46.32
  },
  ...
]
```

来源集合为十日内异动次数至少两次的证券，不包含全市场证券的零计数；不另取实时行情补值。

<a id="api-regulation-deviation"></a>
### `fx.regulation.deviation`

计算单只股票相对所属板块指数的最大上行累计涨跌幅偏离，以及同一区间的上方触发价与剩余涨幅。每个窗口返回当日 `current` 与下一交易日边界 `next_session` 两个场景。

来源：腾讯股票前复权日线（仅 `qfqday` 完全缺键时兼容同份响应的合法不复权 `day`）、前复权历史终值的不复权日线、对应指数不复权日线及股票和指数快照；交易日历同 `fx.reference.trading_calendar`。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 数字字符串，支持沪市 60/68、深市 00/30 开头的股票代码。 |
| `windows` | `list[int] \| tuple[int, ...]` | 可选 | `(10, 30)` | 非空 list/tuple，只允许非布尔整数 10、30，不得重复；保留输入顺序。 |
| `end_date` | `str \| None` | 可选 | `None` | 日期与时刻字符串，格式见[通用约定](#common-conventions)；按真实日历回落到不晚于该自然日的最后交易日。省略时由来源最新有效观察日期确定。 |
| `reset_date` | `str \| None` | 可选，仅限关键字传入 | `None` | 首个重新累计的市场交易日；支持通用约定的六种日期与时刻字符串，验证完整时刻后取日期，不接受 date/datetime 对象。必须由真实日历确认是交易日，不自动休市回落；非交易日为 ValueError，日历损坏或必要输入不可用为 SourceError。 |

**返回：`dict`**

顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 股票代码。 |
| `exchange` | `str` | 股票交易所，sh 或 sz。 |
| `board` | `str` | sse_main_board、star、szse_main_board 或 chinext。 |
| `end_date` | `str` | 实际观察交易日，`YYYY-MM-DD`。 |
| `benchmark` | `dict` | 本次计算的板块基准指数。 |
| `price_basis` | `str` | `qfq_stock_anchored_to_price_date__raw_index`：股票前复权序列锚定到实际终值价格尺度；`raw_stock__raw_index`：实际采用来源不复权股票序列；指数均不复权。 |
| `coverage_status` | `str` | 全部场景的历史覆盖汇总，取值见下方说明。 |
| `inferred_halt_dates` | `list[str]` | 各场景按股票日线缺口推定的停牌日期并集，升序且不重复；不代表交易所确认停牌。 |
| `windows` | `list[dict]` | 按窗口输入顺序，每个窗口依次 current、next_session；默认四条。 |

`benchmark` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 基准指数代码。 |
| `exchange` | `str` | 指数交易所，sh 或 sz。 |
| `name` | `str` | 基准指数名称。 |

`windows` 每条字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `window_days` | `int` | 请求窗口，10 或 30。 |
| `scenario` | `str` | current 或 next_session。 |
| `price_date` | `str` | 股票及指数实际终值日期。 |
| `target_date` | `str` | 候选边界日期；next_session 为下一交易日。 |
| `available_trading_days` | `int` | 窗口内已观察可比统计日数；推定停牌后只计最后一次复牌后的统计日，不含基准点及未来交易日。 |
| `window_status` | `str` | 本场景可用统计日数是否完整及不足原因，取值见下方说明。 |
| `coverage_status` | `str` | 本场景历史覆盖及是否包含推定停牌，取值见下方说明。 |
| `inferred_halt_dates` | `list[str]` | 本场景统计范围及必要基准范围内推定的停牌日期，升序且不重复；无推定日期为 []。 |
| `stock_price` | `float` | 本场景股票实际终值，元/股。 |
| `benchmark_level` | `float` | 本场景指数终值，点。 |
| `stock_price_type` | `str` | daily_close 或 quote。 |
| `benchmark_value_type` | `str` | daily_close 或 quote。 |
| `stock_time` | `str \| None` | 股票报价的来源 ISO 时间，带 +08:00；日线为 None。 |
| `benchmark_time` | `str \| None` | 指数报价的来源 ISO 时间，带 +08:00；日线为 None。 |
| `start_date` | `str` | 最大偏离区间首个统计交易日；reset_not_started 时为尚未开始的重新累计日。 |
| `stock_baseline_date` | `str` | 股票收益基准日期。复牌首日起的候选区间使用停牌前最后一个实际收盘日。 |
| `benchmark_baseline_date` | `str` | 指数收益基准日期。复牌首日起的候选区间使用复牌前一市场交易日；其他候选与股票基准日期相同。 |
| `trading_days` | `int` | 选中区间的已观察统计日数。 |
| `stock_baseline_price` | `float` | 股票收益基准价，按终值尺度锚定，元/股。 |
| `window_start_price` | `float \| None` | start_date 当日的股票价格，按终值尺度锚定，元/股。 |
| `benchmark_baseline_level` | `float` | 指数收益基准点位。 |
| `stock_change_percent` | `float \| None` | 选中区间股票涨跌幅，百分点。 |
| `benchmark_change_percent` | `float \| None` | 选中区间指数涨跌幅，百分点。 |
| `deviation_percent` | `float \| None` | 股票涨跌幅减指数涨跌幅的最大值，百分点，可负。 |
| `threshold_percent` | `int` | 10 日为 100，30 日为 200，百分点。 |
| `theoretical_trigger_price` | `float` | 由选中区间基准计算的未进位理论上方触发价，元/股。 |
| `trigger_price` | `float` | theoretical_trigger_price 向上进位到 0.01 元，元/股。 |
| `remaining_change_percent` | `float` | `(trigger_price / stock_price - 1) × 100`，百分点，可负或为零。 |

**调用与返回示例**

```python
fx.regulation.deviation(code="688175", windows=(10, 30))
```

```text
{
  "code": "688175",
  "exchange": "sh",
  "board": "star",
  "end_date": "2026-10-08",
  "benchmark": {
    "code": "000688",
    "exchange": "sh",
    "name": "科创50"
  },
  "price_basis": "qfq_stock_anchored_to_price_date__raw_index",
  "coverage_status": "complete",
  "inferred_halt_dates": [],
  "windows": [
    {
      "window_days": 10,
      "scenario": "current",
      "price_date": "2026-10-08",
      "target_date": "2026-10-08",
      "available_trading_days": 10,
      "window_status": "complete",
      "coverage_status": "complete",
      "inferred_halt_dates": [],
      "stock_price": 30.94,
      "benchmark_level": 1456.32,
      "stock_price_type": "quote",
      "benchmark_value_type": "quote",
      "stock_time": "2026-10-08T16:14:50+08:00",
      "benchmark_time": "2026-10-08T16:14:12+08:00",
      "start_date": "2026-09-17",
      "stock_baseline_date": "2026-09-16",
      "benchmark_baseline_date": "2026-09-16",
      "trading_days": 10,
      "stock_baseline_price": 17.41,
      "window_start_price": 18.12,
      "benchmark_baseline_level": 1616.19,
      "stock_change_percent": 77.71395749569213,
      "benchmark_change_percent": -9.891782525569395,
      "deviation_percent": 87.60574002126152,
      "threshold_percent": 100,
      "theoretical_trigger_price": 33.09784066229837,
      "trigger_price": 33.1,
      "remaining_change_percent": 6.98125404007757
    },
    ...
  ]
}
```

指定重新累计起点的真实调用与返回节选：

```python
fx.regulation.deviation(
    code="301190", end_date="2026-10-12", reset_date="2026-10-09"
)
```

```text
{
  ...
  "windows": [
    {
      "window_days": 10,
      "scenario": "current",
      "window_status": "partial_after_reset",
      "available_trading_days": 2,
      "start_date": "2026-10-09",
      "stock_baseline_date": "2026-10-08",
      "benchmark_baseline_date": "2026-10-08",
      "deviation_percent": 24.481649885941167,
      "trigger_price": 78.3,
      ...
    },
    ...
  ]
}
```

同次调用的 30 日窗口触发价为 117.82 元。

**必要限制**

基准分别为沪市主板上证 A 指 `000002`、科创板科创 50 `000688`、深市主板深证 A 指 `399107`、创业板创业板综 `399102`。next_session 仅将统计边界移到下一交易日，不预测股价。

历史观察日使用实际日线，股票前复权价格按终值价格尺度锚定；来源最新观察日使用同日有效报价。每个场景选择最大偏离区间，偏离值相同时取最早基准日期，再由该区间计算上方触发价。window_start_price 是窗口起点当日价格，与 stock_baseline_price 不同。

仅当同份响应完全缺少 `qfqday` 键时，可采用合法 `day` 不复权序列，近似当作无需复权；不检查分红或除权，不追加其他来源请求。实际不复权时，历史观察日直接使用该序列的观察日收盘价，最新观察日直接叠加真实同日股票报价，不用 previous_close 对历史价格进行比例桥接。`qfqday` 已存在但为空不回退，None、非法类型或损坏明确失败；多页实际口径不一致不能混拼。回退成功后整次仅发一条标准中文 `UserWarning`，扩取不重复提示，后续计算失败不发成功提示，警告遵循 Python 过滤设置。

`coverage_status` 有四种取值：`complete` 表示历史完整；`short_history` 表示由来源上市日期确认的历史不足；`halt_inferred_from_missing_kline` 表示股票日线内部缺口被推定为停牌；`short_history_and_halt_inferred_from_missing_kline` 表示后两种情况同时存在。顶层汇总所有返回场景的状态，各场景单独标记。

`window_status` 的 `complete` 表示可用统计日数足够；不足时按原因返回 `partial_short_history`、`partial_after_inferred_halt` 或 `partial_short_history_and_inferred_halt`。仅因 reset_date 截短而不足时为 `partial_after_reset`；尚未开始的次一交易日重算场景为 `reset_not_started`。若上市历史不足或推定停牌原因同时适用，优先保留原有不足状态；reset_date 不改变 coverage_status 的来源历史覆盖含义。current 的完整统计日数为 N，next_session 为 N−1 个已观察日；阈值仍为 10 日 100 个百分点、30 日 200 个百分点，不随不足而降低。

`reset_date` 由调用方指定，本接口不读取严重异动名单或公告，也不自动决定公告后的重新累计日。不传或传 None 保持原有滚动计算及请求流程。每个场景按自己的 target_date 判断重算是否生效：current 为观察日，next_session 为真实次一交易日。已生效的起点只有晚于该场景普通窗口首统计日时才截短统计段，统计日不得早于 reset_date，并保留起点前一市场交易日作为真实价格基准；较老起点随窗口滚动退出后不再影响结果。重新累计首日有两个真实价格点时可算一个已观察统计日；仍从同一最大偏离区间计算触发价，平手取最早基准，阈值保持不变。若基准股票价格缺失，沿既有有限扩取与推定停牌规则寻找最后实际股票收盘价，指数基准仍取相应前一市场交易日。

当 reset_date 恰为次一交易日时，current 保持原样；next_session 返回 reset_not_started，available_trading_days 与 trading_days 均为 0，price_date 为真实观察日，target_date 与 start_date 为 reset_date。股票和指数终值、两个基准日期及基准价均采用真实观察日值；window_start_price、stock_change_percent、benchmark_change_percent、deviation_percent 均为 None。沿指数保持观察日水平的条件模型，10 日、30 日理论触发价分别为观察股票价的 2 倍、3 倍，向上取分，remaining_change_percent 相对观察股票价计算；这不是未来价格或已发生收益。reset_date 晚于次一交易日时，两场景均未生效，保持原滚动结果。返回仍为九个顶层字段与每场景二十八个字段，不另返回 reset_date。

重新累计仍须具备必要的统计日价格和真实基准，必要输入不可用时明确报错。重算前已无用途的旧缺价不算作本场景停牌，也不触发停牌提示；实际返回的来源行若损坏，仍整次失败。

只将有前后真实股票价格括住的交易日日线缺口推定为停牌，不填充缺失日线；多次缺口全部记录，只在最后一次推定停牌后的连续交易段内选择最大偏离区间。复牌首日起的区间用停牌前最后一次股票收盘价与复牌前一市场交易日的指数收盘点位作为不同日期的基准；采用前复权时继续按实际终值尺度调整，采用不复权时保持来源价格尺度。其他候选区间的两个基准日期相同。正常与上市短历史场景至少需要两个价格点；复牌首日有真实停牌前股票基准、复牌前指数基准及当日终值时，允许计算一个统计日的收益。

普通调用仍只读取所需窗口；当缺口可能跨过窗口起点或前复权报价缺少桥接基准时，在同次已取得的日历范围内有限补取股票日线。扩取整份替换，并采用最后使用响应的实际复权口径，不混拼价格尺度。上市日期只读取指定代码公司简况中的合法上市日，不依赖行业对比数据；首条日线与上市日前缀仍严格核对。不能找到真实基准、观察日缺少有效价格、指数缺日或必要输入损坏时，整次抛出 SourceError；未知前缀不足不能当作新上市，也不能直接当作停牌。

只在整次计算成功后，针对推定停牌发出一条中文 `UserWarning`（Python 标准用户警告），说明推定日期、受影响的窗口和场景及可用统计日数，并明确尚未核对交易所停牌公告。警告遵循 Python 的过滤设置；无推定停牌时不发此警告。空的 inferred_halt_dates 仅表示未推定出停牌，不代表官方确认无停牌。

计算依据为沪深交易规则中的累计偏离值公式及复牌日起重新计算的规定：[上交所交易规则第 5.4.2、5.4.3 条](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml)、[深交所交易规则第 5.4.3、5.4.5 条](https://docs.static.szse.cn/www/lawrules/rule/trade/W020260424690713155663.pdf)。不同基准日期是以复牌日为区间首日的计算推导；日线缺口是否确为停牌尚未由停牌公告核实。

本接口只提供 current、next_session 上行模型，不包含下行触发价、普通异动累计次数或公告自动清零规则，结果不代表交易所监管认定或停牌结论。日历回退沿用基础工具规则。

<a id="hotlist-data"></a>
## 热榜

<a id="api-hotlist-stocks"></a>
### `fx.hotlist.stocks`

读取当前股票热榜，保留热度、排名变化及来源分析。

来源：同花顺热榜。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `category` | `str` | 可选 | `"popular"` | popular：大家都在看；rising：快速飙升中；new：已发行未上市的新股；technical：技术交易派；value：价值投资派；trend：趋势投资派。 |
| `period` | `str \| None` | 可选 | `None` | 1h 或 24h；popular/rising 默认 1h，两种周期均支持，其余类别默认且仅支持 24h。 |
| `limit` | `int \| None` | 可选 | `20` | 非布尔正整数，最多返回条数；None 返回当前来源提供的完整榜。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 当前所选榜名次。 |
| `code` | `str` | 六位股票代码，保留前导零。 |
| `exchange` | `str` | sh、sz 或 bj。 |
| `name` | `str \| None` | 来源证券名称。 |
| `change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `heat` | `float \| None` | 来源热度，保留原尺度。 |
| `rank_change` | `int \| None` | 排名变化，正数上升、负数下降；0 有效。 |
| `concept_tags` | `list[str] \| None` | 来源概念标签，保持来源顺序。 |
| `popularity_tag` | `str \| None` | 来源状态或类别标签。 |
| `analysis_title` | `str \| None` | 来源分析标题。 |
| `analysis` | `str \| None` | 来源分析原文，保留换行及免责声明。 |
| `search_count` | `int \| None` | 来源搜索次数，不代表独立人数。 |
| `updated_at` | `str \| None` | 来源明确更新时间，带 +08:00 的 ISO 秒时刻。 |
| `issue_pe` | `float \| None` | 新股发行市盈率；其他类别为 None，不是 TTM。 |

**调用与返回示例**

```python
stocks = fx.hotlist.stocks()
```

```text
[
  {
    "rank": 1,
    "code": "600418",
    "exchange": "sh",
    "name": "江淮汽车",
    "change_percent": -9.9919,
    "heat": 1543892.0,
    "rank_change": 0,
    "concept_tags": [
      "百度概念",
      "DeepSeek概念"
    ],
    "popularity_tag": null,
    "analysis_title": "尊界制动支架争议+此前涨幅较大",
    "analysis": "1、据2026年10月8日尊界汽车情况说明，尊界V800制动测试中出现刹车踏板支架断裂，尊界汽车表示将进一步优化部件设计，并为已交付用户提供免费升级选择，相关消息对公司高端车型预期形成扰动。...",
    "search_count": null,
    "updated_at": null,
    "issue_pe": null
  },
  ...
]
```

仅读取当前所选榜，来源榜少于 limit 时返回实际条数；不提供历史日期查询，不保证全部上市股票。

<a id="api-hotlist-sectors"></a>
### `fx.hotlist.sectors`

读取概念、行业或指数板块热榜，保留来源关联 ETF。

来源：同花顺热榜。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `sector_type` | `str` | 可选 | `"concept"` | concept：概念板块；industry：行业板块；index：指数板块。 |
| `limit` | `int \| None` | 可选 | `20` | 非布尔正整数或 None；None 返回当前来源提供的完整榜。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 当前板块榜名次。 |
| `sector_code` | `str` | 来源板块行情代码；指数保留完整市场前缀。 |
| `name` | `str \| None` | 来源板块名称。 |
| `change_percent` | `float \| None` | 板块涨跌幅，百分点。 |
| `heat` | `float \| None` | 来源热度，保留原尺度。 |
| `rank_change` | `int \| None` | 排名变化，正数上升、负数下降。 |
| `tag` | `str \| None` | 来源板块说明。 |
| `hot_tag` | `str \| None` | 来源上榜状态文字。 |
| `related_etf_code` | `str \| None` | 来源关联 ETF 的六位代码。 |
| `related_etf_exchange` | `str \| None` | 关联 ETF 交易所，sh 或 sz。 |
| `related_etf_name` | `str \| None` | 来源关联 ETF 产品名称。 |
| `related_etf_change_percent` | `float \| None` | 关联 ETF 涨跌幅，百分点。 |

**调用与返回示例**

```python
sectors = fx.hotlist.sectors()
```

```text
[
  {
    "rank": 1,
    "sector_code": "886032",
    "name": "固态电池",
    "change_percent": -2.6168,
    "heat": 242640.5,
    "rank_change": 0,
    "tag": "4家涨停",
    "hot_tag": "5天5次上榜",
    "related_etf_code": "159796",
    "related_etf_exchange": "sz",
    "related_etf_name": "电池ETF",
    "related_etf_change_percent": -2.8571
  },
  ...
]
```

sector_code 是行情标识，不能直接传给 fx.sector.ths_concept_quote_snapshot/ths_concept_ohlcv；两者使用概念目录代码。指数榜当前仅提供前 20 窗口，limit=None 也不表示全部指数。

<a id="api-hotlist-convertible_bonds"></a>
### `fx.hotlist.convertible_bonds`

读取当前可转债热榜。

来源：同花顺热榜。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int \| None` | 可选 | `20` | 非布尔正整数或 None；None 返回当前来源提供的完整榜。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 当前转债榜名次。 |
| `code` | `str` | 六位可转债代码。 |
| `exchange` | `str` | sh 或 sz。 |
| `name` | `str \| None` | 来源可转债名称。 |
| `change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `heat` | `float \| None` | 来源热度，保留原尺度。 |

**调用与返回示例**

```python
bonds = fx.hotlist.convertible_bonds()
```

```text
[
  {
    "rank": 1,
    "code": "123268",
    "exchange": "sz",
    "name": "本川转债",
    "change_percent": 7.67,
    "heat": 136033.5
  },
  ...
]
```

仅为来源当前热榜，不表示全部可转债；缺少涨跌幅的合法记录也保留。

<a id="api-hotlist-etfs"></a>
### `fx.hotlist.etfs`

读取所选 ETF 候选池的 24 小时热度排行，保留产品名称与来源标签。

来源：同花顺热榜。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `category` | `str` | 可选 | `"popular"` | popular：24 小时 ETF 热度榜；t0：日内 T+0；price_limit_20：涨跌限制 20%；cross_border：持仓含境外资产；commodity：持仓含大宗商品。 |
| `limit` | `int \| None` | 可选 | `20` | 非布尔正整数或 None；None 返回当前所选池的完整排行。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 所选候选池内的热度名次。 |
| `code` | `str` | 六位 ETF 代码。 |
| `exchange` | `str` | sh 或 sz。 |
| `name` | `str \| None` | 来源 ETF 产品名称。 |
| `change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `heat` | `float \| None` | 来源 24 小时热度，保留原尺度。 |
| `tags` | `list[str] \| None` | 来源展示标签，保持来源顺序并去重。 |

**调用与返回示例**

```python
etfs = fx.hotlist.etfs()
```

```text
[
  {
    "rank": 1,
    "code": "588060",
    "exchange": "sh",
    "name": "科创50ETF广发",
    "change_percent": -3.675676,
    "heat": 15337193.4,
    "tags": [
      "连跌3天",
      "存储芯片"
    ]
  },
  ...
]
```

五类均按对应完整候选池的 24 小时热度降序排列，缺失热度置末，同值按交易所与代码稳定排序。当前来源候选池不保证全部上市 ETF。

<a id="fupan-data"></a>
## 复盘

<a id="api-fupan-jygs_replay"></a>
### `fx.fupan.jygs_replay`

获取韭研公社按题材分组的异动复盘及股票解析，保留来源题材和股票顺序。

来源：[韭研公社异动复盘](https://www.jiuyangongshe.com/action)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `date` | `str \| None` | 可选 | `None` | 日期与时刻字符串，格式见[通用约定](#common-conventions)；省略时使用官网当前复盘，返回来源实际复盘日期。 |
| `session` | `str` | 必需，仅限关键字 | — | 调用者自己的韭研公社 `SESSION` 字符串。 |
| `headless` | `bool` | 可选，仅限关键字 | `False` | 默认显示浏览器窗口；设为 `True` 使用无头模式。仅接受布尔值。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `date` | `str` | 来源实际复盘日期，`YYYY-MM-DD`。 |
| `themes` | `list[dict]` | 题材及股票列表。 |
| `themes[].name` | `str` | 题材名称。 |
| `themes[].reason` | `str \| None` | 题材说明原文。 |
| `themes[].stocks` | `list[dict]` | 该题材的股票与解析。 |
| `themes[].stocks[].code` | `str` | 六位 ASCII 证券代码。 |
| `themes[].stocks[].exchange` | `str` | 交易所，`sh`、`sz` 或 `bj`。 |
| `themes[].stocks[].name` | `str` | 股票名称。 |
| `themes[].stocks[].price` | `float \| None` | 复盘价格，元/股。 |
| `themes[].stocks[].change_percent` | `float \| None` | 涨跌幅，百分点。 |
| `themes[].stocks[].limit_up_time` | `str \| None` | 涨停时刻，`HH:MM:SS`。 |
| `themes[].stocks[].streak_text` | `str \| None` | 连板描述原文。 |
| `themes[].stocks[].explanation` | `str \| None` | 股票解析原文。 |

**调用示例**

```python
import os
from finchx import FinchX

fx = FinchX(timeout=45)
fx.fupan.jygs_replay(
    date="2026-10-13", session=os.environ["JYGS_SESSION"]
)
```

**真实返回节选**

该次调用返回 13 个题材、54 只股票；下例展示首个题材中的一只股票。`explanation` 仅展示首行，接口实际返回完整解析原文。

```json
{
  "date": "2026-10-13",
  "themes": [
    {
      "name": "公告",
      "reason": null,
      "stocks": [
        {
          "code": "600831",
          "exchange": "sh",
          "name": "广电网络",
          "price": 4.3,
          "change_percent": 9.97,
          "limit_up_time": "09:39:06",
          "streak_text": "2天2板",
          "explanation": "预重整+文化传媒+算力+数据中心+AI监管+智慧广电"
        }
      ]
    }
  ]
}
```

**必要限制**

需安装可选 `finchx[jygs]` 及 Chromium，准备方法见 [README](../README.md#安装)；调用时显式传入自己的有效 `SESSION`，认证失效时抛出 `SourceError`。

默认打开临时浏览器窗口，需要可用的图形环境；服务器可显式传入 `headless=True`。每次调用注入 `SESSION` 并执行官网复盘流程，结束后关闭浏览器，不保存登录状态。`FinchX(timeout=45)` 的超时预算由浏览器启动、页面访问和业务响应等待共同使用。错误提示区分执行阶段、HTTP 状态与登录失效，不根据超时判断 IP 是否被封。

仅返回来源提供的异动复盘，不保证包含全市场涨停股票，不另取文章正文。指定日期也可能由官网选择实际复盘日，以返回的 `date` 为准；不自行按工作日回退。涨停时刻缺失的股票仍保留，解析保留来源原文。

<a id="news-data"></a>
## 新闻

<a id="api-news-agp_list"></a>
### `fx.news.agp_list`

获取爱股票快讯正文、标题、关联证券与题材及媒体，按来源顺序返回。

来源：[爱股票快讯](https://www.aigupiao.com/express)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，时间筛选后最多返回的唯一新闻条数。 |
| `since` | `str \| None` | 可选 | `None` | 开始北京时间，接受[通用约定](#common-conventions)中的六种日期与时刻字符串；包含当日或该秒，None 表示无下限。 |
| `until` | `str \| None` | 可选 | `None` | 结束北京时间，格式同上；包含整日或该秒，不得早于 since；None 表示从来源最新新闻开始。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `str` | 来源新闻身份。 |
| `title` | `str \| None` | 来源标题或正文最前明确标出的【标题】；未提供为 None。 |
| `published_at` | `str` | 来源发布时间，ISO 格式，秒精度，带 +08:00。 |
| `content` | `str` | 来源完整快讯文字，保留正文中的【标题】及段落。 |
| `important` | `bool \| None` | 来源是否标为重要。 |
| `url` | `str \| None` | 来源新闻链接。 |
| `related_securities` | `list[dict] \| None` | 关联证券；明确无关联为 []，缺失为 None。 |
| `related_securities[].symbol` | `str` | 来源完整证券标识，保留境内、海外及其他市场标识。 |
| `related_securities[].name` | `str \| None` | 来源证券名称。 |
| `related_themes` | `list[dict] \| None` | 关联题材，不与新闻标题或话题合并。 |
| `related_themes[].id` | `str` | 来源题材身份，不保证是行情板块代码。 |
| `related_themes[].name` | `str \| None` | 来源题材名称。 |
| `related_topics` | `list[dict] \| None` | 关联话题。 |
| `related_topics[].id` | `str` | 来源话题身份。 |
| `related_topics[].name` | `str \| None` | 来源话题标题原文。 |
| `image_urls` | `list[str] \| None` | 来源图片链接；明确无图片为 []。 |
| `video` | `dict \| None` | 来源视频，明确无视频为 None。 |
| `video.url` | `str` | 视频链接。 |
| `video.thumbnail_url` | `str \| None` | 缩略图链接。 |
| `video.cover_url` | `str \| None` | 封面链接。 |
| `video.duration_seconds` | `float \| None` | 来源视频时长，秒。 |
| `attachments` | `list[dict] \| None` | 来源附件；明确无附件为 []。 |
| `attachments[].name` | `str \| None` | 附件名称。 |
| `attachments[].type` | `str \| None` | 来源附件类型。 |
| `attachments[].url` | `str` | 附件链接。 |

**调用与返回示例**

```python
fx.news.agp_list(limit=40)
```

```text
[
  {
    "id": "1556998",
    "title": "美股碳化硅龙头Wolfspeed股价盘前大涨超15%",
    "published_at": "2026-10-08T20:58:07+08:00",
    "content": "【美股碳化硅龙头...",
    "important": true,
    "url": "https://mobile.aigupiao.com/express/detail/id/1556998",
    "related_securities": [],
    "related_themes": [{"id": "1104", "name": "碳化硅"}],
    "related_topics": [],
    "image_urls": [],
    "video": null,
    "attachments": []
  },
  ...
]
```

**必要限制**

`since` / `until` 两端包含，纯日期包含整日，完整时刻按秒筛选。

标题缺失时只读取正文最前的明确【标题】，不由第一句生成标题。关联证券保留原标识，如 USMETA、SI、bj920275，不按六位 A 股代码过滤，也不猜交易所。

仅返回来源当前可提供的快讯。来源耗尽或已越过时间下限时，结果可少于 limit 或为空；来源秒级历史边界不保证覆盖任意日期范围内的全部新闻。

按新闻 ID 去重并保留首次出现的来源顺序，跨页采用后读的业务值。日期分组拼接后的时间乱序不影响合法新闻；时间筛选使用真实发布时间，分页重读交界秒。若来源固定批次停留在同一秒，或返回与已观察边界矛盾的空页，无法确认新闻是否取齐时抛出 SourceError，不跳过潜在遗漏后返回成功。

视频时长以秒为单位，附件仅返回来源链接。

<a id="api-news-bd_list"></a>
### `fx.news.bd_list`

获取百度股市通快讯标题、文字及关联证券，按来源顺序返回。

来源：[百度股市通资讯](https://gushitong.baidu.com/expressnews)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，时间筛选后最多返回的唯一新闻条数。 |
| `since` | `str \| None` | 可选 | `None` | 开始北京时间，接受[通用约定](#common-conventions)中的六种日期与时刻字符串；包含当日或该秒，None 表示无下限。 |
| `until` | `str \| None` | 可选 | `None` | 结束北京时间，格式同上；包含整日或该秒，不得早于 since；None 表示从来源最新新闻开始。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `str` | 来源 loc 原始新闻身份。 |
| `title` | `str \| None` | 来源标题或正文最前明确标出的【标题】；未提供为 None。 |
| `published_at` | `str` | 来源发布时间，ISO 格式，秒精度，带 +08:00。 |
| `content` | `str` | 同份来源响应中的快讯文字。 |
| `important` | `bool \| None` | 来源是否标为重要。 |
| `url` | `str \| None` | 来源给出的第三方新闻链接。 |
| `provider` | `str \| None` | 来源提供方标识，不保证是原创新闻机构。 |
| `tag` | `str \| None` | 来源标签原文。 |
| `related_securities` | `list[dict] \| None` | 关联证券；明确无关联为 []，缺失为 None。 |
| `related_securities[].code` | `str` | 来源证券代码，保留境内及海外市场代码。 |
| `related_securities[].name` | `str \| None` | 来源证券名称。 |
| `related_securities[].market` | `str` | 来源市场标识，如 ab、us、hk，不等同于上市交易所。 |

**调用与返回示例**

```python
fx.news.bd_list(limit=40)
```

```text
[
  {
    "id": "http://dps.baidu.com/data/finance_stock_express_news/7c783a1459d54557e6323b017687c3f7_finance_stock_express_news_aladdin",
    "title": "中文在线：终止2026年度向特定对象发行A股股票事项",
    "published_at": "2026-10-08T20:56:06+08:00",
    "content": "中文在线公告，...",
    "important": false,
    "url": "http://live.financebe.com/stock/detail.html?d=2204965",
    "provider": "Finscope",
    "tag": "快讯$A股",
    "related_securities": [
      {"code": "300364", "name": "中文在线", "market": "ab"},
      {"code": "000001", "name": "上证指数", "market": "ab"}
    ]
  },
  ...,
  {
    "id": "http://live.financebe.com/stock/detail.html?d=2204937",
    "title": null,
    "published_at": "2026-10-08T20:19:13+08:00",
    "content": "谷歌盘前涨超1%，...",
    "important": false,
    "url": "http://live.financebe.com/stock/detail.html?d=2204937",
    "provider": "Finscope",
    "tag": "快讯$美股",
    "related_securities": null
  },
  ...
]
```

**必要限制**

`since` / `until` 两端包含，纯日期包含整日，完整时刻按秒筛选。

历史时间窗需从来源最新记录向前查找，较早的范围可能耗时更长。来源明确耗尽或已越过时间下限时，结果可少于 limit 或为空；不承诺全部新闻历史。

content 只包含百度来源提供的快讯文字，不另取第三方链接正文。标题缺失且正文无明确【标题】时返回 None。

<a id="api-news-em_list"></a>
### `fx.news.em_list`

获取单只股票的东方财富相关文章目录，保留来源新闻及财富号文章，按来源顺序返回。

来源：东方财富个股资讯。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 六位 ASCII 数字字符串，支持沪市 60/68、深市 00/30 开头的股票代码。 |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，时间筛选后最多返回的唯一文章条数。 |
| `since` | `str \| None` | 可选 | `None` | 开始北京时间，接受[通用约定](#common-conventions)中的六种日期与时刻字符串；包含当日或该秒，None 表示无下限。 |
| `until` | `str \| None` | 可选 | `None` | 结束北京时间，格式同上；包含整日或该秒，不得早于 since；None 表示从来源最新文章开始。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `str` | 来源文章身份。 |
| `title` | `str \| None` | 来源文章标题。 |
| `published_at` | `str` | 来源发布时间，ISO 格式，秒精度，带 +08:00。 |
| `url` | `str \| None` | 来源文章链接。 |
| `author` | `str \| None` | 来源目录提供的作者，缺失为 None。 |

**调用与返回示例**

```python
fx.news.em_list(
    code="600519", limit=40, since="2026-10-08", until="2026-10-08"
)
```

```json
[
  {
    "id": "202610083889861528",
    "title": "“茅台自助售货机”现身街头，茅台：未授权，非官方渠道商",
    "published_at": "2026-10-08T20:34:57+08:00",
    "url": "http://finance.eastmoney.com/a/202610083889861528.html",
    "author": null
  },
  {
    "id": "202610083889572316",
    "title": "节庆文旅场景，成酒企动销新主场",
    "published_at": "2026-10-08T14:46:00+08:00",
    "url": "http://finance.eastmoney.com/a/202610083889572316.html",
    "author": null
  }
]
```

**必要限制**

`since` / `until` 两端包含，纯日期包含整日，完整时刻按秒筛选。

仅返回来源当前可提供的个股文章窗口，不保证任意时期的全部历史。历史范围可能耗时更长；来源窗口结束或已越过时间下限时，结果可少于 limit 或为空。

目录保留来源原始文章链接，不含正文；读取正文需链接符合 em_get 支持范围。不因目录作者缺失而从新闻正文猜作者。

<a id="api-news-em_get"></a>
### `fx.news.em_get`

读取东方财富单篇文章的标题、发布时间、正文及正文图片。

来源：东方财富新闻与财富号文章网页。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | 东方财富文章的 http/https 链接：`<频道>.eastmoney.com/a/<id>.html`（频道仅 finance、stock、money、insurance、hk、biz），或 `caifuhao.eastmoney.com/news/<id>`；不含查询参数、片段或端口。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `str` | 同份网页确认的文章身份。 |
| `title` | `str` | 文章头部标题。 |
| `published_at` | `str \| None` | 头部实际发布时间，ISO 格式，带 +08:00，保留分钟或秒精度；仅显示修改时间时为 None。 |
| `source_name` | `str \| None` | 网页来源栏原文，缺失为 None。 |
| `author` | `str \| None` | 网页明确提供的作者，缺失为 None。 |
| `content` | `str` | 文章主体可读文字，保留段落及表格文字。 |
| `image_urls` | `list[str]` | 文章主体图片链接，不含推荐和广告图片。 |

**调用与返回示例**

```python
fx.news.em_get(url="http://finance.eastmoney.com/a/202610083889572316.html")
```

```text
{
  "id": "202610083889572316",
  "title": "节庆文旅场景，成酒企动销新主场",
  "published_at": "2026-10-08T14:46+08:00",
  "source_name": "21世纪经济报道",
  "author": null,
  "content": "21世纪经济报道记者肖夏\n\n这个国庆长假，“回泸重燥”的乐迷被安排得明明白白。...",
  "image_urls": []
}
```

**必要限制**

只读取链接对应的一篇文章，不扩取推荐、评论或广告。列表与正文的来源时间精度可能不同，不为分钟时间补秒；正文记者署名不自动作为 author，不以目录文字补正文。

<a id="articles-data"></a>
## 文章

<a id="api-articles-hot_content"></a>
### `fx.articles.hot_content`

获取同花顺当前热门话题或热门文章，供发现题材及选择阅读内容。

来源：[同花顺热榜](https://eq.10jqka.com.cn/webpage/ths-hot-list/index.html?tabName=redian)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `content_type` | `str` | 可选 | `"topic"` | `"topic"` 为热门话题，`"article"` 为热门文章。 |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，最多返回的唯一业务条数。 |

**返回：`list[dict]`**

热门话题每行固定八个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 来源榜单顺序对应的名次。 |
| `title` | `str \| None` | 来源话题或专题标题；缺失为 None。 |
| `summary` | `str \| None` | 来源话题说明，不是文章正文。 |
| `subtitle` | `str \| None` | 来源独立副标题。 |
| `heat` | `float \| None` | 当前话题榜的来源热度。 |
| `url` | `str` | 话题目录或单页专题链接。 |
| `target_type` | `str` | `topic_list` 交给 ths_list；`content` 交给 ths_get。 |
| `related_securities` | `list[dict] \| None` | 来源关联证券；缺失为 None，明确空数组为 []。 |

关联证券每行固定四个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 来源证券代码。 |
| `exchange` | `str \| None` | 交易所 sh 或 sz；其他来源市场为 None。 |
| `name` | `str` | 来源证券名称。 |
| `change_percent` | `float \| None` | 来源涨跌幅，百分点。 |

热门文章每行固定六个字段，按来源名次升序返回：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `rank` | `int` | 来源热门文章名次。 |
| `title` | `str \| None` | 来源文章标题；缺失为 None。 |
| `heat` | `float \| None` | 当前文章榜的来源热度。 |
| `tag` | `str \| None` | 官网显示的“评论火爆”或“点赞激增”标签。 |
| `url` | `str` | 公开文章链接，可交给 ths_get。 |
| `related_entities` | `list[dict] \| None` | 来源证券、行业、概念等关联对象。 |

热门文章的关联对象每行固定四个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 来源原始标识。 |
| `name` | `str` | 来源名称。 |
| `market` | `str \| None` | 来源市场标记，不等同交易所；缺失为 None。 |
| `change_percent` | `float \| None` | 来源涨跌幅，百分点；未提供为 None。 |

**调用与返回示例**

```python
fx.articles.hot_content(content_type="topic", limit=3)
```

```text
[
  {
    "rank": 1,
    "title": "固态电池板块再度走强",
    "summary": "固态电池概念盘中走强，多股涨停，政策推动规模化应用。你认为该趋势对相关板块带动潜力如何？",
    "subtitle": null,
    "heat": 912705.0,
    "url": "https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=Tv47iqu",
    "target_type": "topic_list",
    "related_securities": [
      {"code": "002074", "exchange": "sz", "name": "国轩高科", "change_percent": null}
    ]
  },
  ...
]
```

```python
fx.articles.hot_content(content_type="article", limit=3)
```

```text
[
  {
    "rank": 1,
    "title": "美股半导体、光通信板块，集体下跌",
    "heat": 41244.974500923,
    "tag": null,
    "url": "https://stock.10jqka.com.cn/20261009/c680496918.shtml",
    "related_entities": [
      {"code": "881129", "name": "通信设备", "market": "48", "change_percent": null},
      {"code": "881121", "name": "半导体", "market": "48", "change_percent": null},
      ...
    ]
  },
  ...
]
```

榜单热度与顺序随来源变化，两个榜单的热度不可直接比较。来源耗尽时可少于 limit；热门文章仅覆盖来源当前排名窗口，不保证全站或全部历史。榜单不含正文，阅读单篇内容使用 ths_get。

<a id="api-articles-ths_list"></a>
### `fx.articles.ths_list`

读取一个同花顺社区话题关联的新闻与社区文章目录，包含观点，按来源顺序返回。

来源：[同花顺社区](https://t.10jqka.com.cn/)话题目录。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `topic_url` | `str` | 必需 | — | 同花顺社区 Tcode 话题 URL，支持桌面 `/lgt/main/frontend-main-service/topic/index.html?code=T...` 和手机 `/m/topic/index.html?code=T...`。 |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，最多返回的唯一文章条数。 |

**返回：`list[dict]`**

每行固定七个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | `str` | 同花顺公开文章链接，可传入 ths_get。 |
| `content_type` | `str` | `news` 为新闻，`article` 为社区文章，包含观点。 |
| `title` | `str \| None` | 来源文章标题。 |
| `published_at` | `str \| None` | 来源完整发布时间，带 +08:00 的 ISO 字符串。 |
| `source_name` | `str \| None` | 来源明确提供的新闻媒体名称。 |
| `author` | `str \| None` | 来源明确发布账号。 |
| `summary` | `str \| None` | 来源摘要，仅规范文字及换行。 |

**调用与返回示例**

```python
fx.articles.ths_list(
    topic_url="https://t.10jqka.com.cn/lgt/main/frontend-main-service/topic/index.html?code=Tv47iqu",
    limit=4,
)
```

```text
[
  {
    "url": "https://news.10jqka.com.cn/mobile/news/article/v1/encoded/a0e38678246048836a5",
    "content_type": "news",
    "title": "固态电池概念盘中持续走高，多股收获涨停，力王股份30cm涨停",
    "published_at": "2026-10-08T10:21:00+08:00",
    "source_name": "财闻",
    "author": null,
    "summary": "10月8日，固态电池概念盘中持续走高，力王股份(920627.BJ)30cm涨停，此前金银河(300619.SZ)、紫竹高科(002058.SZ)、丰元股份(002805.SZ)、雄韬股份(002733.SZ)、传艺科技(002866."
  },
  {
    "url": "https://t.10jqka.com.cn/pid_700648219.shtml",
    "content_type": "article",
    "title": "固态电池概念表现活跃，七部门出台十五五电池规划",
    "published_at": "2026-10-08T10:35:38+08:00",
    "source_name": null,
    "author": "每经ETF风向标",
    "summary": "截至10月8日10时17分，固态电池概念表现活跃，固态电池含量超82%、全市场领先的创业板电池ETF（158079）跟踪指数上涨2.2%，新能源ETF华安（51"
  },
  ...
]
```

目录包含新闻和社区文章（含观点），不含正文或讨论帖；返回 url 可传入 ths_get。来源耗尽时可少于 limit 或为空，不保证全部历史。六位股票或概念代码、深度专题和活动页不能作为 topic_url。目录与详情各保自身来源时间及精度。

<a id="api-articles-ths_get"></a>
### `fx.articles.ths_get`

读取同花顺单篇公开新闻、社区文章（含观点）、视频或专题的正文及媒体。

来源：[同花顺新闻](https://news.10jqka.com.cn/)及[同花顺社区](https://t.10jqka.com.cn/)公开内容。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | 同花顺已支持的公开内容 URL；可直接使用 hot_content 或 ths_list 返回的文章链接。 |

**返回：`dict`**

固定十三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `content_type` | `str` | `news`、`article`、`video` 或 `topic`。 |
| `title` | `str \| None` | 同份来源标题。 |
| `published_at` | `str \| None` | 来源完整发布时间，带 +08:00 的 ISO 字符串；保留实际精度。 |
| `source_time` | `str \| None` | 来源缺年份、相对时间等不完整时间原文。 |
| `source_name` | `str \| None` | 来源明确媒体名称。 |
| `author` | `str \| None` | 来源明确作者或发布账号。 |
| `original_url` | `str \| None` | 来源明确原文链接。 |
| `content` | `str \| None` | 主体可读正文，保留段落及表格文字。 |
| `image_urls` | `list[str]` | 主体图片链接。 |
| `video_urls` | `list[str]` | 来源明确视频链接。 |
| `cover_url` | `str \| None` | 来源明确封面链接。 |
| `disclaimer` | `str \| None` | 来源明确免责声明。 |
| `related_entities` | `list[dict] \| None` | 来源证券、行业、概念等关联对象；缺失为 None，明确空数组为 []。 |

关联对象每行固定三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 来源原始标识。 |
| `name` | `str \| None` | 来源名称；缺失为 None。 |
| `market` | `str` | 来源市场标记，不等同交易所。 |

**调用与返回示例**

```python
fx.articles.ths_get(
    url="https://news.10jqka.com.cn/mobile/news/article/v1/encoded/a0e38678246048836a5"
)
```

```text
{
  "content_type": "news",
  "title": "固态电池概念盘中持续走高，多股收获涨停，力王股份30cm涨停",
  "published_at": "2026-10-08T10:20:40+08:00",
  "source_time": null,
  "source_name": "财闻",
  "author": null,
  "original_url": "https://www.caiwennews.com/article/1639346.shtml",
  "content": "10月8日，固态电池概念盘中持续走高，力王股份(920627.BJ)30cm涨停，...",
  "image_urls": [],
  "video_urls": [],
  "cover_url": null,
  "disclaimer": "风险提示：本文内容仅供参考，不代表同花顺观点。...",
  "related_entities": [
    {"code": "002058", "name": "紫竹高科", "market": "33"},
    {"code": "920627", "name": "力王股份", "market": "151"},
    ...
  ]
}
```

```python
fx.articles.ths_get(url="https://t.10jqka.com.cn/pid_700648219.shtml")
```

```text
{
  "content_type": "article",
  "title": "固态电池概念表现活跃，七部门出台十五五电池规划",
  "published_at": null,
  "source_time": "10-08 10:35",
  "source_name": null,
  "author": "每经ETF风向标",
  "original_url": null,
  "content": "截至10月8日10时17分，固态电池概念表现活跃，...",
  "image_urls": [],
  "video_urls": [],
  "cover_url": "https://i.thsi.cn/sns/circle/wapcircle/img2/calfgame/ths_logo.png",
  "disclaimer": null,
  "related_entities": null
}
```

普通新闻支持 `<频道>.10jqka.com.cn/YYYYMMDD/c<ID>.shtml`，频道为 news、stock、goodsfu、invest、field、fund 或 fe，也支持 news.10jqka.com.cn 的 encoded 新闻链接。社区支持 `/pid_<ID>.shtml`、`/m/zhibo/pid_<ID>.shtml`、观点 `/lgt/short_view/index.html?pid=<ID>` 及 `/m/post/articleShare/articleshare.html?pid=...`、`/lgt/share_page/articleShare.html?pid=...&type=circle` 分享页；专题支持 mams.10jqka.com.cn 的 `/new/server/html/<ID>.html` 和 news.10jqka.com.cn 的 `/deep-topic/topic/dt_...` 模板。其他主机、讨论帖、Tcode 目录及孤立 mp contentId 链接不在支持范围。

发布时间保留来源实际精度；缺完整日期时 published_at 为 None，source_time 保留时间原文。图片或视频内容可没有文字。

<a id="api-articles-agp_topic_articles"></a>
### `fx.articles.agp_topic_articles`

获取爱股票题材频道文章，包含来源正文，按来源最新或热门顺序返回。

来源：[爱股票题材频道](https://www.aigupiao.com/)。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，总计最多返回的唯一文章条数。 |
| `sort` | `str` | 可选 | `"newest"` | `"newest"` 为来源最新顺序，`"hot"` 为来源热门顺序。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | `str` | 来源公开文章链接，可传入 agp_get。 |
| `title` | `str \| None` | 来源标题，缺失为 None。 |
| `published_at` | `str \| None` | 来源发布时间，ISO 格式，带 +08:00，保留来源精度。 |
| `author` | `str \| None` | 来源明确发布账号或作者。 |
| `summary` | `str \| None` | 来源提供的摘要。 |
| `content` | `str \| None` | 来源可读正文，保留段落和表格文字。 |
| `image_urls` | `list[str]` | 来源正文及业务图片链接，按来源顺序去重。 |
| `audio_url` | `str \| None` | 来源明确公开音频链接，无者为 None。 |
| `category` | `str \| None` | 来源文章分类名称。 |
| `topics` | `list[str] \| None` | 来源关联话题名称。 |
| `related_securities` | `list[dict] \| None` | 来源明确关联的境内外证券。 |
| `related_securities[].symbol` | `str` | 来源证券标识，如 sh600026、bj920522、CL。 |
| `related_securities[].name` | `str \| None` | 来源证券名称。 |

**调用与返回示例**

```python
fx.articles.agp_topic_articles(limit=25)
```

```text
[
  {
    "url": "https://www.aigupiao.com/dynamic/detail/5792378",
    "title": "油运暴涨，轮到造船？",
    "published_at": "2026-10-08T20:52:00+08:00",
    "author": "主线纪要",
    "summary": "主线纪要｜美银研报发布于10月6日...",
    "content": "主线纪要｜美银研报发布于10月6日...",
    "image_urls": [...],
    "audio_url": null,
    "category": "题材行业",
    "topics": [],
    "related_securities": [
      {"symbol": "sh600026", "name": "中远海能"},
      ...,
      {"symbol": "CL", "name": "原油"},
      ...
    ]
  },
  ...
]
```

**必要限制**

limit 是总返回上限；来源耗尽时可更少或为空，不保证全部题材历史。热门顺序随来源变化。列表已含来源公开可读正文，标题与摘要缺失时不从正文生成。无图片时 image_urls 为 []。

<a id="api-articles-agp_get"></a>
### `fx.articles.agp_get`

读取爱股票单篇公开文章，保留来源提供的正文、平台摘要与免责声明。

来源：[爱股票](https://www.aigupiao.com/)公开文章。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | www.aigupiao.com 的 http/https 文章 URL 字符串，支持 `/dynamic/detail/<id>`、`/view/detail/<id>` 及旧版 `/Dynamic/user_dynamic_detail?o_id=<id>` 链接；不含其他查询参数、片段或端口。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `str \| None` | 来源文章标题，缺失为 None。 |
| `published_at` | `str \| None` | 来源发布时间，ISO 格式，带 +08:00，保留来源精度。 |
| `author` | `str \| None` | 来源明确发布账号或作者。 |
| `summary` | `str \| None` | 本篇来源提供的摘要。 |
| `content` | `str \| None` | 文章主体可读正文，保留段落和表格文字。 |
| `image_urls` | `list[str]` | 正文及明确业务图片链接，按来源顺序去重。 |
| `audio_url` | `str \| None` | 来源明确公开音频链接，无者为 None。 |
| `category` | `str \| None` | 来源文章分类名称。 |
| `topics` | `list[str] \| None` | 来源关联话题名称。 |
| `related_securities` | `list[dict] \| None` | 来源明确关联的境内外证券。 |
| `related_securities[].symbol` | `str` | 来源证券标识，保留原市场前缀或境外代码。 |
| `related_securities[].name` | `str \| None` | 来源证券名称。 |
| `ai_summary` | `str \| None` | 来源明确提供的平台 AI 摘要。 |
| `disclaimer` | `str \| None` | 来源免责声明原文。 |

**调用与返回示例**

```python
fx.articles.agp_get(url="https://www.aigupiao.com/dynamic/detail/5792378")
```

```text
{
  "title": "油运暴涨，轮到造船？",
  "published_at": "2026-10-08T20:52:00+08:00",
  "author": "主线纪要",
  "summary": null,
  "content": "主线纪要｜美银研报发布于10月6日...",
  "image_urls": [...],
  "audio_url": "https://igp-img-upload-1251605428.cos.ap-shanghai.myqcloud.com/baidu/6ac791f539e2970001ee45f6.mp3",
  "category": "题材行业",
  "topics": [],
  "related_securities": [
    {"symbol": "sh600026", "name": "中远海能"},
    ...,
    {"symbol": "CL", "name": "原油"},
    ...
  ],
  "ai_summary": "海峡风险拖慢油轮周转，...",
  "disclaimer": "以上内容仅作为投资参考，..."
}
```

**必要限制**

只读取来源公开可读的本篇内容，不扩取推荐、评论或受限全文。详情与频道正文可能相同，缺失字段不从频道回填。无图片时 image_urls 为 []。

<a id="disclosure-data"></a>
## 公告

<a id="api-disclosure-em_list"></a>
### `fx.disclosure.em_list`

读取股票公告目录，可按数量、北京时间范围和公告分类筛选。

来源：东方财富公告。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `code` | `str` | 必需 | — | 沪市 60/68、深市 00/30 开头的六位 ASCII 股票代码字符串。 |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，筛选后最多返回的唯一公告条数。 |
| `since` | `str \| datetime.date \| None` | 可选 | `None` | 时间下限；接受[通用约定](#common-conventions)中的六种日期与完整时刻字符串或 `datetime.date`，包含边界。 |
| `until` | `str \| datetime.date \| None` | 可选 | `None` | 时间上限；类型同 since，纯日期包含整日，不得早于 since。 |
| `categories` | `list[str] \| tuple[str, ...] \| None` | 可选 | `None` | 不限定分类，或下列分类名称组成的非空 list/tuple；多个分类按 OR 筛选，不接受单字符串。 |

支持以下二十种分类：

- 重大事项、重大合同、投资相关、股权激励。
- 财务报告、定期报告、利润分配、业绩预告、业绩快报。
- 融资公告、增发、新股发行、配股。
- 风险提示。
- 资产重组、要约收购、吸收合并、回购。
- 信息变更、持股变动。

**返回：`list[dict]`**

每行固定七个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `str` | 来源 AN 公告标识。 |
| `title` | `str \| None` | 来源公告标题。 |
| `notice_date` | `str \| None` | 公告日期，YYYY-MM-DD。 |
| `source_time` | `str \| None` | 来源时刻，带 +08:00 的 ISO 字符串，保留来源实际精度。 |
| `url` | `str` | 官方公告链接，可传入 em_get。 |
| `categories` | `list[dict] \| None` | 公告实际分类，区别于请求的筛选标签。 |
| `related_securities` | `list[dict] \| None` | 来源全部关联证券，保留境内外身份。 |

公告实际分类每行固定两个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str \| None` | 来源分类代码。 |
| `name` | `str \| None` | 来源分类名称。 |

关联证券每行固定三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 来源证券代码，保留前导零。 |
| `market` | `str` | 来源市场标记，不等同交易所。 |
| `name` | `str \| None` | 来源证券名称。 |

**调用与返回示例**

```python
notices = fx.disclosure.em_list(code="300308", limit=2)
```

```json
[
  {
    "id": "AN202610081830198767",
    "title": "中际旭创:H股公告(截至2026年9月30日止股份发行人的证券变动月报表)",
    "notice_date": "2026-10-08",
    "source_time": "2026-10-08T07:56:41.000+08:00",
    "url": "https://data.eastmoney.com/notices/detail/300308/AN202610081830198767.html",
    "categories": [
      {
        "code": "001002008",
        "name": "其他"
      }
    ],
    "related_securities": [
      {
        "code": "300308",
        "market": "0",
        "name": "中际旭创"
      }
    ]
  },
  {
    "id": "AN202609301830044481",
    "title": "中际旭创:关于协议受让北京中石伟业科技股份有限公司部分股权完成过户登记的公告",
    "notice_date": "2026-10-01",
    "source_time": "2026-09-30T16:24:04.000+08:00",
    "url": "https://data.eastmoney.com/notices/detail/300308/AN202609301830044481.html",
    "categories": [
      {
        "code": "001002007003005",
        "name": "股权转让"
      }
    ],
    "related_securities": [
      {
        "code": "300308",
        "market": "0",
        "name": "中际旭创"
      }
    ]
  }
]
```

**必要限制**

`since` / `until` 两端包含，纯日期包含整日，完整时刻按秒筛选。

优先按 source_time 筛选，缺失时按 notice_date 自然日筛选。source_time 不代表首次发布时间。单一分类或未限定分类时保持来源顺序，多个独立分类按公告日期倒序返回，缺失日期置末；来源耗尽时可少于 limit 或为空，不保证全部历史。

<a id="api-disclosure-em_get"></a>
### `fx.disclosure.em_get`

读取单篇公告的来源正文及附件链接，保留来源关联证券。

来源：东方财富公告。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | 已支持的东方财富公告 URL：当前或旧版公告页、手机公告页，以及具有 AN 标识的 H2/H22 附件链接。 |

**返回：`dict`**

固定六个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `str \| None` | 同份来源公告标题。 |
| `notice_date` | `str \| None` | 同份来源公告日期，YYYY-MM-DD。 |
| `source_time` | `str \| None` | 同份来源时刻，带 +08:00 的 ISO 字符串；不代表首次发布时间。 |
| `content` | `str \| None` | 来源完整正文，仅客观规范换行；有有效附件的公告可无正文。 |
| `related_securities` | `list[dict] \| None` | 来源全部关联证券；字段同上方关联证券表。 |
| `attachments` | `list[dict] \| None` | 来源附件链接，按来源顺序去重。 |

附件每行固定三个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | `str` | 来源原始附件链接，保留查询参数。 |
| `size_kb` | `int \| None` | 来源显示大小，KB；有效零值保留。 |
| `type` | `str \| None` | PDF 为 pdf；缺失或含义未确认时为 None。 |

**调用与返回示例**

```python
notice = fx.disclosure.em_get(url=notices[0]["url"])
```

```text
{
  "title": "中际旭创:H股公告(截至2026年9月30日止股份发行人的证券变动月报表)",
  "notice_date": "2026-10-08",
  "source_time": "2026-10-08T07:56:41+08:00",
  "content": "股份發行人及根據《上市規則》第十九B章上市的香港預託證券發行人的證券變動月報表\n...",
  "related_securities": [
    {
      "code": "03308",
      "market": "116",
      "name": "中际旭创"
    },
    {
      "code": "300308",
      "market": "0",
      "name": "中际旭创"
    }
  ],
  "attachments": [
    {
      "url": "https://pdf.dfcfw.com/pdf/H2_AN202610081830198767_1.pdf?1791446201000.pdf",
      "size_kb": 159,
      "type": "pdf"
    }
  ]
}
```

也可按支持的附件链接读取对应公告的来源文字：

```python
notice = fx.disclosure.em_get(
    url="https://pdf.dfcfw.com/pdf/H22_AN201708160804547103_1.pdf?1672840143000.pdf"
)
```

```text
{
  "title": "深发展A(0001)2000年年度报告",
  "notice_date": "2001-04-14",
  "source_time": "2017-08-16T18:03:17+08:00",
  "content": "深发展A(0001)2000年年度报告\n...",
  "related_securities": [
    {
      "code": "000001",
      "market": "0",
      "name": "平安银行"
    }
  ],
  "attachments": [
    {
      "url": "https://pdf.dfcfw.com/pdf/H22_AN201708160804547103_1.pdf?1672840143000.pdf",
      "size_kb": 235,
      "type": "pdf"
    }
  ]
}
```

**必要限制**

支持 data.eastmoney.com 的 `/notices/detail/<code>/<AN>.html` 和旧版 `/notices/detail/<AN>.html`、np-info.eastmoney.com 的 `/wap/notice/?infocode=<AN>`，以及 pdf.dfcfw.com 的 `/pdf/H2_<AN>_<序号>.pdf`、H22 同形链接；PDF 链接可带来源数字时间戳查询。上述链接接受 http/https，不接受用户信息、端口或片段；其他主机、路由或查询参数不在支持范围。

正文来自来源已有文字，不下载或解析 PDF、图片等附件。详情各字段只取本次来源，不从目录补值；日期与来源时刻分别保留实际口径及精度。

<a id="reports-data"></a>
## 研报

<a id="api-reports-fetch"></a>
### `fx.reports.fetch`

一次搜索多个来源的研报，自动读取选中报告的网页摘要或正文及可用 PDF 链接。无需再逐篇调用详情接口。

来源：爱股票、东方财富、易观。关键词交给各来源自己的搜索接口，不下载全部目录后在本地匹配。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `keyword` | `str` | 必需 | — | 非空搜索关键词。匹配范围由各来源决定，标题未包含关键词的来源搜索结果也保留。 |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，按标题和机构去重后最多返回的研报条数。 |
| `start_date` | `str \| None` | 可选 | `None` | 发布日期下界，包含当日；支持通用六种日期/时刻字符串，验证时刻后按日筛选。 |
| `end_date` | `str \| None` | 可选 | `None` | 发布日期上界，包含当日；格式同上，不能早于 start_date。 |

**返回：`dict`**

固定 `reports`、`errors` 两个字段。`reports` 是报告列表，每条固定八个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source` | `str` | 数据来源：`aigupiao`、`eastmoney` 或 `analysys`。 |
| `title` | `str \| None` | 研报标题，去除搜索高亮标签。 |
| `institute` | `str \| None` | 来源明确给出的研究机构。 |
| `publication_date` | `str \| None` | 来源明示的完整发布日期，YYYY-MM-DD；不拿收录时间补年份。 |
| `url` | `str` | 原网页链接。 |
| `content` | `str \| None` | 网页内容客观转换的 Markdown，保留段落、标题及真实图片链接，不生成摘要、不做图片文字识别。 |
| `content_type` | `str \| None` | `summary` 为来源网页摘要，`webpage` 为网页正文（可包含纯图报告的图片链接）；未取得内容为 None。 |
| `pdf_urls` | `list[str] \| None` | 来源实际提供的 PDF 链接；已读取详情但无链接为 []，详情未成功读取时为 None。 |

`errors` 为错误列表，全部正常时是 []。每条只有 `source`、`url`、`reason`：分别是来源、失败报告链接和中文原因；来源搜索失败时 url 为 None。部分来源或详情失败时保留已确认的报告，并在 errors 中说明；三个来源都未取得有效搜索响应时抛出 `FinchXError`，可从其 errors 属性查看各来源的 `SourceError`。合法的无匹配结果返回空列表。

**调用与返回示例**

```python
fx = FinchX(timeout=30)
result = fx.reports.fetch(keyword="易观", limit=3)
```

```text
{
  "reports": [
    {
      "source": "analysys",
      "title": "破解具身数据瓶颈：造、治、用、通怎么做？——《中国具身智能数据产业分析报告2026》解读六",
      "institute": "易观",
      "publication_date": "2026-10-09",
      "url": "https://www.analysys.cn/article/detail/20021521",
      "content": "# 易观分析：具身数据当前的核心矛盾，已不再是“数据总量不够”，而是“量、质、异构”三重结构性卡点相互纠缠、彼此放大。...",
      "content_type": "webpage",
      "pdf_urls": []
    },
    ...
  ],
  "errors": []
}
```

**读取范围**

三个来源并发检索，各自顺序翻页，先筛日期、再收集所需候选。允许正常的跨页重叠和数量变化。

所有来源的报告，只要非空 `title` 和 `institute` 两字段完全相同，就合并为一条；日期、来源、网页或 PDF 地址不同不影响去重。标题或机构缺失时保留独立记录，不把未知值当作同一篇报告。

每组保留发布日期较新的整条记录；同日依次优先详情未失败、详情已确认、正文和 PDF 链接更齐全的记录，再按爱股票、东方财富、易观及来源内首次顺序选择。`source`、`url`、`content` 和附件均保留所选记录的实际信息，不跨记录拼正文。最终按发布日期降序排列，未知日期放在末尾；去重不足 limit 时继续读取后续页，直到达到数量、来源结束或明确失败。来源搜索顺序可能与发布日期不同，不承诺全库最新前 N 篇。

有日期条件时，无法确认完整发布日期的报告不进入结果；需要时读取同篇详情确认日期。来源耗尽时允许少于 limit，不设置固定扫描条数。网页摘要不是 PDF 全文；PDF 仅返回链接，可另行传给 `fx.reference.pdf_text`。

易观旧版报告的图片列表及原生 PDF 附件也会读取；图片只保留链接，不识别图片内文字。来源只有摘要或 PDF 时按实际能力返回，不补造全文。

检索阶段和详情阶段分别使用客户端 timeout 作为时间预算；预算用完时保留已确认结果并说明错误。单次调用耗时可能超过 timeout，进行中的网络读取不保证能立即中断。

<a id="api-reports-agp_list"></a>
### `fx.reports.agp_list`

读取研报目录，可按类别、关键词或行业筛选。

来源：爱股票研报。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int` | 可选 | `20` | 非布尔正整数，最多返回的唯一研报条数。 |
| `kind` | `str` | 可选 | `"all"` | all：全部；stock：个股；industry：行业。 |
| `keyword` | `str \| None` | 可选 | `None` | 来源模糊搜索关键词，最多 2000 字符，去首尾空白，不接受控制字符；不保证精确股票匹配。 |
| `industry` | `str \| None` | 可选 | `None` | 当前来源行业的精确名称或字符串代码，如汽车行业或 000039；保留代码前导零，不能与 kind='stock' 同用。 |

**返回：`list[dict]`**

每行固定十一个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | `str` | 本篇研报详情链接，可传入 agp_get。 |
| `title` | `str \| None` | 来源独立标题。 |
| `kind` | `str \| None` | 来源研报类别，不按请求参数猜分类。 |
| `ref_code` | `str \| None` | 关联股票或行业的来源代码，保留前导零。 |
| `name` | `str \| None` | 来源股票或行业名称。 |
| `institute` | `str \| None` | 来源研究机构。 |
| `rating` | `str \| int \| float \| None` | 来源评级原值，不转换数字枚举；有效 0 与空文字保留。 |
| `publication_date_text` | `str \| None` | 来源日期文字；仅有月日时不补年份。 |
| `recorded_at` | `str \| None` | 平台收录时刻，带 +08:00 的 ISO 字符串，保留来源精度。 |
| `symbol` | `str \| None` | 来源完整股票或行业标识，如 sh603499、in000039。 |
| `theme_id` | `int \| str \| None` | 来源板块跳转标识，不等同研报或行业代码；有效 0 保留。 |

**调用与返回示例**

```python
reports = fx.reports.agp_list(limit=1)
```

```json
[
  {
    "url": "http://101.35.29.159:82/report/detail_m.php?id=2477185",
    "title": "汽车行业周报：“金九”车企销量分化，关注出海进展",
    "kind": "industry",
    "ref_code": "000039",
    "name": "汽车行业",
    "institute": "华龙证券",
    "rating": "推荐",
    "publication_date_text": "10-09",
    "recorded_at": "2026-10-09T08:40:02.000+08:00",
    "symbol": "in000039",
    "theme_id": 950
  }
]
```

**必要限制**

industry 按当前来源行业匹配；指定行业时 all 按行业查询。recorded_at 是平台收录时刻，不代表研报发布日期，不用于补 publication_date_text 的年份。保持来源顺序，来源耗尽时可少于 limit 或为空；不保证全部历史或同秒记录完备。

<a id="api-reports-agp_get"></a>
### `fx.reports.agp_get`

独立读取单篇研报的网页摘要、发布日期与原 PDF 链接。

来源：爱股票研报。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | 列表返回的 `http://101.35.29.159:82/report/detail_m.php?id=<ASCII数字>` 链接。 |

**返回：`dict`**

固定六个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `str \| None` | 本次网页独立标题。 |
| `publication_date` | `str \| None` | 网页明示的完整发布日期，YYYY-MM-DD。 |
| `institute` | `str \| None` | 网页研究机构。 |
| `researcher` | `str \| None` | 网页研究员原文。 |
| `summary` | `str \| None` | 网页摘要，仅客观规范文字和换行；有 PDF 时可无摘要。 |
| `pdf_urls` | `list[str]` | 原 PDF 链接，保持来源顺序、去除重复地址；无链接为 []。 |

**调用与返回示例**

```python
report = fx.reports.agp_get(url=reports[0]["url"])
```

```text
{
  "title": "汽车行业周报：“金九”车企销量分化，关注出海进展",
  "publication_date": "2026-10-09",
  "institute": "华龙证券",
  "researcher": "李浩洋",
  "summary": "摘要：\n本周观点：“金九”车企销量分化，关注出海进展。...",
  "pdf_urls": [
    "https://pdf.dfcfw.com/pdf/H3_AP202610091830233649_1.pdf?1791533487000.pdf"
  ]
}
```

**必要限制**

仅支持上述官方详情路由，不接受其他主机、路径、端口、额外查询或片段。摘要不是 PDF 全文，PDF 只返回链接，不下载或解析附件；字段只取本次网页，不从列表补标题、机构或日期。

<a id="forum-data"></a>
## 论坛

<a id="api-forum-tgb_replies"></a>
### `fx.forum.tgb_replies`

读取当前账户关注动态中的回复与发布文章，返回完整正文及回复明确引用的父回复全文。

来源：淘股吧。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | `int \| None` | 可选 | `20` | 非布尔正整数或 `None`，时间筛选后最多返回的唯一内容数，回复与文章合计；`None` 遍历当前账户可见的全部匹配内容。 |
| `since` | `str \| datetime.date \| None` | 可选 | `None` | 北京时间下界，日期与时刻格式见[通用约定](#common-conventions)，也支持 `datetime.date`；纯日期包含整日。 |
| `until` | `str \| datetime.date \| None` | 可选 | `None` | 北京时间上界，两端包含；不得早于 `since`，也支持 `datetime.date`。 |
| `cookies` | `str \| Mapping[str, str]` | 必需，仅限关键字 | — | 调用者自己的非空登录 Cookie 字符串或字符串键值字典，仅用于当次官方请求。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `reply_id` | `str` | 回复为来源原编号；文章为 `topic:<文章编号>`，与回复编号区分。 |
| `user_id` | `str \| None` | 发布用户身份。 |
| `username` | `str \| None` | 发布用户名。 |
| `reply_time` | `str \| None` | 回复或文章发布动态时刻，带 `+08:00` 的 ISO 字符串，保留来源分钟或秒精度。 |
| `content` | `str \| None` | 回复全文，或文章正式标题加空行及全文；纯图片回复可为空，纯图片文章保留标题。 |
| `image_urls` | `list[str]` | 正文图片链接，无图片为 `[]`。 |
| `post_url` | `str` | 所属主题链接。 |
| `url` | `str` | 定位回复或文章的链接；文章与 `post_url` 相同。 |
| `parent_reply_id` | `str \| None` | 引用父回复的身份，来源未提供或无引用时为 `None`。 |
| `parent_username` | `str \| None` | 被引用回复的用户名。 |
| `parent_content` | `str \| None` | 被引用回复全文；无引用或纯图片引用可为空。 |
| `parent_image_urls` | `list[str] \| None` | 被引用回复的图片链接，无引用为 `None`，有引用且无图片为 `[]`。 |

**调用与返回示例**

```python
import os
from finchx import FinchX

fx = FinchX()
replies = fx.forum.tgb_replies(
    limit=20, cookies=os.environ["TGB_COOKIES"]
)
```

```text
[
  {
    "reply_id": "103546742",
    "user_id": "2577911",
    "username": "zarili",
    "reply_time": "2026-10-09T09:08:47+08:00",
    "content": "今天大概率还是观望的一天，昨天指数破3800之后又被拉起来了，依然有护盘的因素。这样护着会让这个调整时间拖久一些。对于指数的预期，最差的预期就是回到7月的低点附近构筑双底，也就是向下空间没有很大，在企稳之前继续看，先不动手",
    "image_urls": [],
    "post_url": "https://www.tgb.cn/a/2vajtjAsuS2",
    "url": "https://www.tgb.cn/a/2vajtjAsuS2/103546742#103546742",
    "parent_reply_id": null,
    "parent_username": null,
    "parent_content": null,
    "parent_image_urls": null
  },
  {
    "reply_id": "103543459",
    "user_id": "8808042",
    "username": "洛飞超短笔记",
    "reply_time": "2026-10-08T23:39:36+08:00",
    "content": "周五思路\n\n弱势环境，情绪负反馈收敛但无明显增量，目前的情绪题材 小周期概率大，小周期特征 新题材持续性和连板高度一般，所以明天再去接力四进五 盈亏比说不好。固态今天高潮，明天分歧预期，后面等时代断板再看板块是否二波，地产后面弱轮动概率大 没太多交易性。药，新周期不开始 药不容易结束 明天药如果延续分歧 看低xi机会 直接修复不追，独立逻辑的善水，如果明天大跌 后面等止跌做出监管，如果强势承接 异动不跌 或许还有向上预期。\n\n弱势环境，降低仓位，降低预期，聚焦核心，谨慎开仓，防守大于进攻的阶段，空仓等后面指数止跌共振的新周期也没问题。\n\n祝好！",
    "image_urls": [],
    "post_url": "https://www.tgb.cn/a/2vIcb0QPJZz",
    "url": "https://www.tgb.cn/a/2vIcb0QPJZz/103543459#103543459",
    "parent_reply_id": null,
    "parent_username": null,
    "parent_content": null,
    "parent_image_urls": null
  },
  {
    "reply_id": "103543436",
    "user_id": "8808042",
    "username": "洛飞超短笔记",
    "reply_time": "2026-10-08T23:38:17+08:00",
    "content": "量还在，也不一定结束。21年新能源见顶之后，题材股开启21-22大牛市，浙江建投 九安医疗 中通客车等，很多短线选手改变命运。资金会找到出路的，不悲观。",
    "image_urls": [],
    "post_url": "https://www.tgb.cn/a/2vIcb0QPJZz",
    "url": "https://www.tgb.cn/a/2vIcb0QPJZz/103543436#103543436",
    "parent_reply_id": null,
    "parent_username": "独智行者",
    "parent_content": "创业板3个月-30%跌幅，牛市幻想破灭了",
    "parent_image_urls": []
  },
  ...
]
```

文章调用与返回节选：

```python
fx.forum.tgb_replies(
    limit=1,
    since="2026-10-12 18:44:22",
    until="2026-10-12 18:44:22",
    cookies=os.environ["TGB_COOKIES"],
)
```

```text
[
  {
    "reply_id": "topic:8806616",
    ...
    "reply_time": "2026-10-12T18:44:22+08:00",
    "content": "2026年10月12日 明天开始，为国护盘\n\n当下这个盘面很想说不要慌，...",
    "image_urls": [],
    "post_url": "https://www.tgb.cn/a/2vPYh4TFgxS",
    "url": "https://www.tgb.cn/a/2vPYh4TFgxS",
    "parent_reply_id": null,
    "parent_username": null,
    "parent_content": null,
    "parent_image_urls": null
  }
]
```

**必要限制**

`since` / `until` 两端包含，纯日期包含整日，完整时刻按秒筛选。

只返回当前账户关注动态可遍历的回复和发布文章，不承诺全站或全部历史；来源耗尽可少于 `limit`。默认返回全文，不以动态摘要回填无法取得的正文或引用；认证失效或必要正文不可用时明确失败。文章的四个 `parent_*` 字段均为 `None`。Cookie 不写入配置、日志或返回结果，图片仅返回链接。

同一回复在页面重复展示且业务信息一致时合并。正文、图片或展开状态有冲突时，由官方全文接口确认，不按页面出现次序或文字长短选择。只有能确认与目标及必要父回复无关的页面异常才可跳过；必要回复的主题或引用身份冲突、无法确定引用归属时明确报错，不能丢弃引用后返回成功。

<a id="iwencai-data"></a>
## 问财

<a id="api-iwencai-select"></a>
### `fx.iwencai.select`

按自然语言条件选股，保留来源中文指标名称、日期和单位。

来源：同花顺问财。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `query` | `str` | 必需 | — | 非空选股条件字符串。 |
| `limit` | `int` | 可选 | `100` | 非布尔正整数，最多返回的唯一股票数，不接受 `None`。 |
| `cookies` | `str \| Mapping[str, str]` | 必需，仅限关键字 | — | 调用者自己的非空 Cookie 字符串或字符串键值字典，仅用于当次请求。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `str` | 六位 ASCII 股票代码。 |
| `exchange` | `str` | 交易所，`sh`、`sz` 或 `bj`。 |
| `name` | `str \| None` | 股票名称。 |
| 来源中文指标列 | 来源 JSON 类型 | 随条件变化的业务指标，保留来源列名、日期、单位与值，不改为标准行情字段。 |

**调用与返回示例**

```python
import os
from finchx import FinchX

fx = FinchX()
stocks = fx.iwencai.select(
    query="成交额排名前500，非ST", limit=100, cookies=os.environ["IWENCAI_COOKIES"]
)
```

```text
[
  {
    "code": "300308",
    "exchange": "sz",
    "name": "中际旭创",
    "涨跌幅(%)": -5.38825,
    "成交额(元)[20261009]": 14385905933.93,
    "现价(元)": "740.81",
    "成交量(股)[20261009]": "19156344",
    "振幅(%)[20261009]": 6.385696,
    "换手率(%)[20261009]": 1.7260000000000002
  },
  {
    "code": "300750",
    "exchange": "sz",
    "name": "宁德时代",
    "涨跌幅(%)": 4.18483,
    "成交额(元)[20261009]": 11257951283.47,
    "现价(元)": "298.75",
    "成交量(股)[20261009]": "38153575",
    "振幅(%)[20261009]": 4.3312990000000005,
    "换手率(%)[20261009]": 0.8959999999999999
  },
  {
    "code": "300502",
    "exchange": "sz",
    "name": "新易盛",
    "涨跌幅(%)": -5.96037,
    "成交额(元)[20261009]": 9898043080.4,
    "现价(元)": "355.94",
    "成交量(股)[20261009]": "27335019",
    "振幅(%)[20261009]": 6.5786,
    "换手率(%)[20261009]": 2.179
  },
  ...
]
```

仅取来源当前可提供的匹配股票，不承诺全部历史或稳定快照。Cookie 不写入配置、日志或返回结果。

<a id="api-iwencai-search"></a>
### `fx.iwencai.search`

按来源语义顺序搜索研报、公告或新闻。

来源：同花顺问财。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `query` | `str` | 必需 | — | 非空搜索字符串。 |
| `channel` | `str` | 可选 | `"report"` | `report` 研报、`announcement` 公告或 `news` 新闻。 |
| `limit` | `int` | 可选 | `50` | 非布尔整数，范围 1 至 50。 |
| `api_key` | `str` | 必需，仅限关键字 | — | 调用者自己的非空 API Key 字符串，仅用于当次请求。 |

**返回：`list[dict]`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `uid` | `str` | 来源文档身份。 |
| `title` | `str \| None` | 来源标题。 |
| `published_at` | `str \| None` | 来源完整日期或北京时间 ISO 时刻，保留实际精度，不给纯日期补零时。 |
| `url` | `str \| None` | 来源文档链接。 |
| `score` | `float \| None` | 来源语义得分，保留有效 `0`。 |

**调用与返回示例**

```python
import os
from finchx import FinchX

fx = FinchX()
reports = fx.iwencai.search(
    query="汽车行业", limit=50, channel="report",
    api_key=os.environ["IWENCAI_API_KEY"]
)
```

```text
[
  {
    "uid": "20f4305609ad1ea0",
    "title": "汽车行业周报",
    "published_at": "2026-06-08T00:00:00+08:00",
    "url": "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=20f4305609ad1ea0",
    "score": 0.12064447
  },
  {
    "uid": "1b41e234ef24d4fe",
    "title": "汽车行业周报",
    "published_at": "2026-07-06T00:00:00+08:00",
    "url": "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=1b41e234ef24d4fe",
    "score": 0.11985513
  },
  {
    "uid": "8be6ac8604e63d54",
    "title": "汽车行业周报",
    "published_at": "2026-03-30T00:00:00+08:00",
    "url": "https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=8be6ac8604e63d54",
    "score": 0.11491687
  },
  ...
]
```

保持来源语义顺序，不另按日期排序；仅返回本次来源搜索窗口，不承诺分页或全部匹配文档。API Key 必须显式传入，不从环境变量兜底，也不写入配置、日志或返回结果。

<a id="api-iwencai-get_report"></a>
### `fx.iwencai.get_report`

读取链接对应的研报、公告或新闻正文及可用元信息。

来源：同花顺问财文字快照或链接对应的网页。

**参数**

| 参数 | 类型 | 是否必需 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | 必需 | — | HTTP(S) 正文或 PDF 链接。 |
| `uid` | `str \| None` | 可选，仅限关键字 | `None` | 搜索结果文档编号，配合 `channel` 优先读取问财文字正文。 |
| `channel` | `str \| None` | 可选，仅限关键字 | `None` | 搜索分类：`report`、`announcement` 或 `news`。 |

**返回：`dict`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | `str \| None` | 来源标题。 |
| `publication_date` | `str \| None` | 来源明确的日期或北京时间 ISO 时刻，保留实际精度，纯日期不补时刻。 |
| `institute` | `str \| None` | 来源研究机构；新闻、公告等未提供时为 None。 |
| `researcher` | `str \| None` | 来源研究员原文，未提供时为 None。 |
| `content` | `str \| None` | 来源可读正文，保留文字与段落；仅有 PDF 时为 None。 |
| `original_url` | `str \| None` | 来源原文链接；PDF 为实际文件链接。 |
| `file_type` | `str \| None` | 来源文件类型。 |

**调用与返回示例**

```python
from finchx import FinchX

fx = FinchX()
report = fx.iwencai.get_report(
    url="https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=d9924066929303a3"
)
```

```text
{
  "title": "业绩持续高增，全球光互连龙头地位稳固",
  "publication_date": "2026-09-09",
  "institute": "天风证券",
  "researcher": "王奕红",
  "content": "事件：公司发布2026年半年度报告，实现营业收入417.78亿元（YoY+182.49%），归母净利润136.51亿元（YoY+241.70%）。...",
  "original_url": null,
  "file_type": "pdf"
}
```

也可直接读取新浪等来源网页：

```python
report = fx.iwencai.get_report(
    "https://stock.finance.sina.com.cn/stock/go.php/vReport_Show/kind/search/rptid/843913684309/index.phtml"
)
```

```text
{
  "title": "汽车行业：2026年上半年汽车行业运行态势、竞争格局及发展展望",
  "publication_date": "2026-09-28",
  "institute": "大公国际资信评估有限公司",
  "researcher": "许晨晨",
  "content": "2026 年上半年，我国汽车行业整体呈现总量承压、结构优化、...",
  "original_url": null,
  "file_type": null
}
```

搜索后可将同一结果的 `uid` 与分类一同传入，优先读取研报或公告的文字快照：

```python
import os
from finchx import FinchX

fx = FinchX()
channel = "announcement"
items = fx.iwencai.search(
    query="中际旭创", channel=channel, api_key=os.environ["IWENCAI_API_KEY"]
)
for item in items:
    if item["url"] is not None:
        document = fx.iwencai.get_report(
            item["url"], uid=item["uid"], channel=channel
        )
        print(document["content"] or document["original_url"])
```

字段取正文来源，可选信息缺失为 None。正文不含图片中的文字；PDF 只返回链接，`content=None`。来源限制访问时可能无法读取。
