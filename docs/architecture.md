# 运行架构

平台按信号计算、回测执行、实验编排、工作台服务四层组织。

`quantlab/factors.py` 读取行情矩阵并输出与行情对齐的信号分数。`quantlab/engine.py` 只接收外部信号，负责逐日推进账户、交易约束、估值和绩效。`scripts/study.py` 编排开发期参数比较、参数冻结、验证和图表输出；`scripts/research.py` 生成横截面因子统计。

工作台的 `api.py` 提供页面、任务和结果接口，请求模型由 `schemas.py` 管理。`jobs.py` 将任务存入 SQLite，并使用单队列启动 `worker.py` 独立进程。每个任务的输入、进度、成交和净值都保存在自己的目录。服务启动时自动发现 `artifacts/runs/*/request.json`，将仓库内的完成结果载入工作台。

前端为本地 HTML/CSS/JavaScript，收益率和回撤由真实净值数据绘制成 SVG，支持悬停查询、日期筛选、多策略对比、分页和 CSV 下载。界面与 API 同源，由一个 Python 服务提供。

## 目录职责

- `feathers`：外部只读行情，不进入 Git。
- `configs`：可复现的研究参数。
- `artifacts/development`：每组开发实验的净值和指标。
- `artifacts/runs`：全区间、验证期、初始版和迭代版的完整账户产物。
- `artifacts/research`：因子统计数据。
- `artifacts/screenshots`：真实工作台页面截图。
- `.web-state`：本机任务数据库和界面提交的回测结果，不进入 Git。

## 工作流

启动工作台 → 查看已载入成果 → 新建或复制配置 → 队列执行 → 查看收益率、成交和持仓 → 导出数据。研究批处理与交互回测复用同一引擎。
