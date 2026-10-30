"""执行固定开发/验证流程，保存选参轨迹、账户产物和工作台可导入记录。"""
import argparse
import sys
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from quantlab.engine import Config, load_data, run, save_result
from quantlab.factors import FactorLibrary
from quantlab.paths import ROOT, data_directory

LABELS = {"mom_60_skip5": "60日动量", "breakout_60": "60日突破", "low_vol_momentum": "低波动动量"}
COLORS = {"mom_60_skip5": "#496bc0", "breakout_60": "#c79535", "low_vol_momentum": "#16836a"}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def metrics(result, strategy, phase, version):
    s=result[-1]
    return dict(strategy=strategy, name=LABELS[strategy], phase=phase, version=version,
                top_n=s["config"]["top_n"], rebalance=s["config"]["rebalance"],
                **{k:s[k] for k in ("start","end","total_return","annual_return","sharpe","max_drawdown","total_fees","trades","final_equity")})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="三策略参数迭代与固定验证")
    parser.add_argument("--data")
    parser.add_argument("--config",default=str(ROOT/"configs/study.json"))
    args=parser.parse_args()
    settings=json.loads(Path(args.config).read_text(encoding="utf-8"))
    output=ROOT/"artifacts"
    output.mkdir(exist_ok=True)
    write_json(output/"study_plan.json",settings)
    folder=data_directory(args.data)
    raw=load_data(folder)
    dates=raw["close"].index
    sessions=dates[(dates>=settings["start"])&(dates<=settings["end"])]
    manifest=dict(source="feathers", first_session=str(sessions[0].date()), last_session=str(sessions[-1].date()),
                  sessions=len(sessions), stocks=len(raw["close"].columns),
                  sessions_by_year={str(k):int(v) for k,v in pd.Series(sessions.year).value_counts().sort_index().items()},
                  files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open("rb"),"sha256").hexdigest()) for p in sorted(folder.glob("*.feather"))})
    write_json(output/"data_manifest.json",manifest)
    # 预热行情仅供历史窗口计算；资金记账严格从配置开始日推进。
    data={k:v.loc["2024-07-01":settings["end"]].copy() for k,v in raw.items()}
    del raw
    library=FactorLibrary(data)
    common={k:settings[k] for k in Config.__dataclass_fields__ if k in settings and k not in {"top_n","rebalance"}}
    train_rows=[]
    selected={}
    signals={}
    for strategy in settings["strategies"]:
        print(f"开发区间：{strategy}",flush=True)
        signals[strategy]=library.get(strategy)
        candidates=[]
        for n,interval in product(settings["top_n"],settings["rebalance"]):
            cfg=Config(**{**common,"end":settings["train_end"],"top_n":n,"rebalance":interval})
            result=run(data,cfg,scores=signals[strategy])
            row=metrics(result,strategy,"development","baseline" if (n,interval)==(50,5) else "candidate")
            candidates.append(row)
            train_rows.append(row)
            destination=output/"development"/f"{strategy}_n{n}_r{interval}"
            destination.mkdir(parents=True,exist_ok=True)
            result[0].to_csv(destination/"equity.csv",encoding="utf-8",index=True)
            write_json(destination/"summary.json",result[-1])
            print(f"  N={n}, R={interval}: 收益 {row['total_return']:.2%}, 夏普 {row['sharpe']:.3f}",flush=True)
        best=max(candidates,key=lambda r:(r["sharpe"] if r["sharpe"] is not None else -np.inf,r["max_drawdown"],-r["total_fees"]))
        selected[strategy]=dict(top_n=best["top_n"],rebalance=best["rebalance"])
    # 在读取验证成绩之前持久化参数，验证阶段不再修改。
    write_json(output/"selected_parameters.json",dict(selection=settings["selection"],development_end=settings["train_end"],parameters=selected))
    pd.DataFrame(train_rows).to_csv(output/"development_grid.csv",index=False,encoding="utf-8")
    rows=[]
    curves={"full":{},"validation":{}}
    for strategy,params in selected.items():
        for phase,start,end,version,parameters in [
            ("full",settings["start"],settings["end"],"selected",params),
            ("validation",settings["validation_start"],settings["end"],"selected",params),
            ("validation",settings["validation_start"],settings["end"],"baseline",dict(top_n=50,rebalance=5))]:
            print(f"执行：{strategy} / {phase} / {version}",flush=True)
            cfg=Config(**{**common,"start":start,"end":end,**parameters})
            result=run(data,cfg,scores=signals[strategy])
            destination=output/"runs"/f"{strategy}_{phase}_{version}"
            save_result(result,destination)
            name=f"{LABELS[strategy]} · {'全区间' if phase=='full' else '2026验证'} · {'迭代版' if version=='selected' else '初始版'}"
            write_json(destination/"request.json",dict(name=name,strategy=strategy,config=asdict(cfg)))
            rows.append(metrics(result,strategy,phase,version))
            if version=="selected": curves[phase][strategy]=result[0]
    pd.DataFrame(rows).to_csv(output/"strategy_summary.csv",index=False,encoding="utf-8")
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei"],"axes.unicode_minus":False,"font.size":11})
    for phase,items in curves.items():
        fig,axes=plt.subplots(2,1,figsize=(14,8),sharex=True,gridspec_kw={"height_ratios":[3,1]})
        for i,(strategy,nav) in enumerate(items.items()):
            line=["-","--","-."][i]
            axes[0].plot(nav.index,nav.nav-1,label=f"{LABELS[strategy]}  {nav.nav.iloc[-1]-1:.2%}",color=COLORS[strategy],linestyle=line,lw=1.8)
            axes[1].plot(nav.index,nav.drawdown,color=COLORS[strategy],linestyle=line,lw=1.2)
        axes[0].set_title("三策略累计收益率 · "+("2025—2026年9月" if phase=="full" else "2026年1—9月固定验证"),loc="left",fontweight="bold",pad=16)
        axes[0].set_ylabel("累计收益率")
        axes[1].set_ylabel("回撤")
        for ax in axes:
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(axis="y",alpha=.18)
            ax.spines[["top","right"]].set_visible(False)
            ax.axhline(0,color="#999999",lw=.7)
        axes[0].legend(loc="upper left",frameon=False)
        axes[1].set_xlim(sessions[0] if phase=="full" else items[next(iter(items))].index[0],sessions[-1])
        fig.tight_layout()
        fig.savefig(output/f"{phase}_comparison.png",dpi=160)
        plt.close(fig)
    print(pd.DataFrame(rows).to_string(index=False),flush=True)


if __name__=="__main__":
    main()
