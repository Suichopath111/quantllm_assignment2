"""独立回测子进程，原子写入可轮询的进度。"""
import argparse
import json
import sys
import traceback
import time
from pathlib import Path
from quantlab.engine import Config, load_data, run, save_result
from quantlab.factors import FactorLibrary


def execute(data_dir, output):
    output=Path(output)
    payload=json.loads((output/"request.json").read_text(encoding="utf-8"))
    def progress(value, stage):
        temporary=output/"progress.tmp"
        temporary.write_text(json.dumps(dict(progress=round(value,4),stage=stage),ensure_ascii=False),encoding="utf-8")
        # Windows 上读句柄短暂占用目标文件时重试，进度写入失败不应终止交易模拟。
        for attempt in range(10):
            try:
                temporary.replace(output/"progress.json")
                break
            except PermissionError:
                time.sleep(.02)
    progress(.02,"读取本地行情")
    data=load_data(data_dir)
    progress(.12,"计算策略信号")
    scores=FactorLibrary(data).get(payload["strategy"])
    progress(.22,"逐日撮合与记账")
    result=run(data,Config(**payload["config"]),scores=scores,progress_callback=lambda value:progress(.22+.72*value,"逐日撮合与记账"))
    progress(.96,"保存回测结果")
    save_result(result,output)
    progress(1,"回测完成")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    try:
        execute(args.data,args.output)
    except Exception as exc:
        (Path(args.output)/"error.json").write_text(json.dumps({"error":str(exc)},ensure_ascii=False),encoding="utf-8")
        traceback.print_exc()
        sys.exit(1)
