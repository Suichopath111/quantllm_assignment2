# 工作台

执行 `python app.py --data ../feathers`，打开 http://127.0.0.1:8765 。API 文档在 `/docs`。

支持策略总览、回测队列、三策略曲线对比、因子实验室、数据中心、成交和持仓查询，以及 CSV 导出。仓库自带成果启动即载入。

自定义端口：`python app.py --port 8766`。自定义本地状态目录：`python app.py --state D:/quantlab-state`。数据目录也可通过 `QUANTLAB_DATA` 指定。

截图：安装 `playwright` 后运行 `python scripts/capture_workbench.py`，页面图片保存到 `artifacts/screenshots`。
