# QuantLab · A 股策略研究工作台

基于本地 Feather 行情的日频策略研究平台。提供策略配置、异步回测、收益率曲线、组合对比、因子统计、成交查询与结果导出。

本次完成 2025-01-01 至 2026-09-30 的三策略研究，覆盖 424 个交易日。成果见 [策略研究报告](artifacts/REPORT.md)。

![工作台收益率曲线](artifacts/screenshots/comparison_full.png)

## 启动

Python 3.10+，在项目目录执行：

```powershell
python -m pip install -r requirements.txt
python app.py --data "E:\大四上\当代量化系统\feathers"
```

打开 http://127.0.0.1:8765 。默认会寻找启动目录、项目内或项目旁的 `feathers`，也可使用 `QUANTLAB_DATA` 环境变量。原命令 `python server.py` 保持可用。

行情目录包含 `open.feather`、`close.feather`、`high.feather`、`low.feather`、`cumadj.feather`、`amt.feather`。宽表第一列为 `date`，其余为股票代码。行情保存在项目外，运行产物自动写入 `artifacts`，本地任务写入 `.web-state`。仓库自带的三策略结果在首次启动时自动载入。

## 策略研究

```powershell
python study.py --data "E:\大四上\当代量化系统\feathers"
python research.py --data "E:\大四上\当代量化系统\feathers"
```

`configs/study.json` 固定三组策略、开发和验证日期、持仓数、调仓频率及费用参数。先在 2025 年运行 12 组参数实验，按开发期扣费夏普选参，保存参数后执行 2026 年 1—9 月验证和全区间展示。2024 年下半年行情用于历史窗口预热，账户收益从指定研究区间开始计算。

- 60 日动量：跳过最近 5 日，按复权价格历史收益排序。
- 60 日突破：收盘价相对于此前 60 日最高价，窗口排除当日高价。
- 低波动动量：20 日低波动排名与跳过 5 日的 60 日动量排名相加。

## 项目结构

```text
app.py                 工作台统一入口
paths.py               数据和产物路径
engine.py              撮合、费用、账户、估值与绩效
factors.py             因子信号库
study.py               参数迭代、冻结和验证编排
research.py            IC、分组收益与研究统计
run.py                 外部信号命令行入口
webapp/
  api.py               页面与结果接口
  schemas.py           请求模型
  jobs.py              SQLite 任务记录和进程队列
  worker.py            独立回测进程
  catalog.py           策略目录
  static/              工作台前端
configs/study.json     可复现研究配置
artifacts/             实验、结果、报告、图表、截图
scripts/               浏览器截图工具
docs/                  架构和交易计算说明
```

## 成果索引

- [研究报告与策略迭代](artifacts/REPORT.md)
- [全区间收益率图](artifacts/full_comparison.png)
- [固定验证收益率图](artifacts/validation_comparison.png)
- [策略指标 CSV](artifacts/strategy_summary.csv)
- [开发期全部参数](artifacts/development_grid.csv)
- [冻结参数](artifacts/selected_parameters.json)
- [数据指纹](artifacts/data_manifest.json)
- [架构说明](docs/architecture.md)
- [交易与指标定义](docs/execution.md)

项目不包含测试文件。运行依赖集中在 `requirements.txt`；浏览器截图工具额外使用 `playwright` 和本机 Chrome。
