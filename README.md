# FinchX

FinchX 是面向 A 股的 Python 数据接口，提供行情、资金流、公司与财务资料，以及新闻、公告、研报等数据。完整接口、参数和业务字段见 [API 文档](https://github.com/sanshi2026/FinchX/blob/main/docs/API.md)。

接口直接返回原生 `dict` 或 `list`，便于查询、分析和接入自己的交易研究流程。

## FinchX 3.0

FinchX 3.0 相对旧版有重大更新：重构接口架构与业务分类，统一参数规范，重新核对数据字段、单位和来源语义，并加强完整性校验与错误处理。**强烈推荐旧版用户升级到 3.1。**

**3.0 的接口、参数和返回结构与 2.x 不兼容。** 请保留旧环境，在独立环境按 API 文档逐项迁移调用和字段读取。

3.1 新增 `fx.reports.fetch`，按关键词聚合爱股票、东方财富和易观研报，自动获取来源提供的摘要或正文及 PDF 链接。

3.1.1 新增 `fx.reports.agp_fetch`、`fx.reports.em_fetch` 和 `fx.reports.analysys_fetch`，支持各来源无关键词目录获取和关键词搜索。四个研报接口统一按完全相同的标题、机构和发布日期去重，保留跨日同名报告；三个独立接口的客户端超时按每次 HTTP 请求计算。原 `fx.reports.agp_list` 和 `fx.reports.agp_get` 已由 `fx.reports.agp_fetch` 替代，自动完成目录和详情读取。

3.1.2 新增 `fx.fupan.jygs_replay_ego`，复用 Ego Lite 中的韭研公社登录状态，返回结构与原复盘接口相同。热榜接受来源提供的合法正整数市场类别，修复市场值 `22` 导致整榜失败的问题。论坛接口新增可选 `on_missing_reply` 回调，可处理官网主题页和精确回复页均成功读取但目标回复缺失的情况。

**3.1.2 热榜返回字段有变化：**股票、可转债和 ETF 热榜删除 `exchange`，板块热榜删除 `related_etf_exchange`；读取这些字段的调用代码需要同步调整。ETF 同热度时按证券代码、完整来源市场身份稳定排序。详细字段与回调规则见 [API 文档](https://github.com/sanshi2026/FinchX/blob/main/docs/API.md)。

3.1.3 为 `fx.market.ohlcv` 增加同花顺 HXKline 日线来源，可通过 `source="tonghuashun"` 选择，原有调用仍默认使用腾讯。`FinchX(use_proxy=False)` 可让该实例的 HTTP 请求绕过系统和环境代理，默认仍使用代理。

3.1.4 支持同花顺北交所财务报表、腾讯新增指数分时、东财监管名单中的转债，并让新闻、公告和话题目录按来源分页状态读取，不再受固定页数上限影响。

## 安装

安装：

```bash
python -m pip install finchx
```
需要 Python 3.10 或更新版本。建议使用独立虚拟环境。

已有用户升级到 3.1.4：

```bash
python -m pip install --upgrade 'finchx==3.1.4'
```

按需安装可选依赖：`calendar` 用于离线交易日历及自动日历回退，`pdf` 用于 PDF 文字层和原生书签提取，`jygs` 用于原韭研复盘接口 `fx.fupan.jygs_replay`。可组合安装，只保留需要的项：

```bash
python -m pip install --upgrade 'finchx[calendar,pdf,jygs]==3.1.4'
```

使用 `fx.fupan.jygs_replay` 还须在同一 Python 环境安装 Chromium，并在调用时传入自己的 `SESSION`：

```bash
python -m playwright install chromium
```

使用 `fx.fupan.jygs_replay_ego` 时，先安装并启动 Ego Lite，确保 `ego-browser` 命令可用，并在 Ego Lite 中登录韭研公社。

## 快速开始

查询当前涨幅排名前五的股票：

```python
from finchx import FinchX

fx = FinchX(timeout=15.0)
rows = fx.market.ranking(limit=5)
print(rows)
```

每次调用重新取数，不提供结果缓存或文件保存。字段、单位、缺失值和认证要求请按各接口文档处理。
