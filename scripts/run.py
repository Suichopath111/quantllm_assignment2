"""命令行入口。"""
import argparse
from pathlib import Path
import json
import pandas as pd
from quantlab.engine import Config, load_data, run, save_result
from quantlab.paths import data_directory, ROOT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A 股外部信号回测")
    parser.add_argument("--data", default=str(data_directory()))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "external-signals"))
    parser.add_argument("--scores", required=True, help="信号宽表 CSV：date 列和股票代码列，分数越高越优")
    parser.add_argument("--metadata", help="可选逐日状态 CSV，字段见 README")
    for name, field in Config.__dataclass_fields__.items():
        parser.add_argument("--" + name.replace("_", "-"), type=field.type, default=field.default)
    args = vars(parser.parse_args())
    data_path, output, metadata = (args.pop(k) for k in ("data", "output", "metadata"))
    scores = pd.read_csv(args.pop("scores"), encoding="utf-8-sig", parse_dates=["date"]).set_index("date")
    result = run(load_data(data_path), Config(**args), pd.read_csv(metadata) if metadata else None, scores=scores)
    save_result(result, output)
    print(json.dumps(result[-1], ensure_ascii=False, indent=2))
