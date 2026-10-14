# FinchX

FinchX 是面向 A 股的 Python 数据接口，提供行情、资金流、公司与财务资料，以及新闻、公告、研报等数据。完整接口、参数和业务字段见 [API 文档](https://github.com/sanshi2026/FinchX/blob/main/docs/API.md)。

接口直接返回原生 `dict` 或 `list`，便于查询、分析和接入自己的交易研究流程。

## FinchX 3.0

FinchX 3.0 相对旧版有重大更新：重构接口架构与业务分类，统一参数规范，重新核对数据字段、单位和来源语义，并加强完整性校验与错误处理。**强烈推荐旧版用户升级到 3.1。**

**3.0 的接口、参数和返回结构与 2.x 不兼容。** 请保留旧环境，在独立环境按 API 文档逐项迁移调用和字段读取。

3.1 新增 `fx.reports.fetch`，按关键词聚合爱股票、东方财富和易观研报，自动获取来源提供的摘要或正文及 PDF 链接，并按完全相同的标题和机构去重。

## 安装

安装：

```bash
python -m pip install finchx
```
需要 Python 3.10 或更新版本。建议使用独立虚拟环境。

已有用户升级到 3.1：

```bash
python -m pip install --upgrade 'finchx==3.1.0'
```

按需安装可选依赖：`calendar` 用于离线交易日历及自动日历回退，`pdf` 用于 PDF 文字层和原生书签提取，`jygs` 用于韭研复盘。可组合安装，只保留需要的项：

```bash
python -m pip install --upgrade 'finchx[calendar,pdf,jygs]==3.1.0'
```

使用韭研复盘还须在同一 Python 环境安装 Chromium，并在调用时传入自己的 `SESSION`：

```bash
python -m playwright install chromium
```

## 快速开始

查询当前涨幅排名前五的股票：

```python
from finchx import FinchX

fx = FinchX(timeout=15.0)
rows = fx.market.ranking(limit=5)
print(rows)
```

每次调用重新取数，不提供结果缓存或文件保存。字段、单位、缺失值和认证要求请按各接口文档处理。
