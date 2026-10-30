# 因子研究

运行 `python research.py --data ../feathers`，生成指定研究区间内的三组因子统计，工作台的因子实验室自动读取 `artifacts/research`。

运行 `python study.py --data ../feathers`，执行三策略参数迭代。参数见 `configs/study.json`，全部结果见 [研究报告](artifacts/REPORT.md)。

因子分数均以高分优先，信号与股票池只使用对应日期及以前的行情。标签定义和交易指标见 [计算说明](docs/execution.md)。
