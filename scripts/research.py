"""三策略因子研究：同一股票池下的横截面IC与分组收益。"""
import argparse
import sys
import json
import numpy as np
import pandas as pd
from quantlab.engine import load_data
from quantlab.factors import FactorLibrary
from quantlab.paths import ROOT, data_directory

def evaluate(score, labels, eligible, factor, dates, min_cross=30):
    rows, daily = [], []
    score = score.where(eligible)
    periods = {"all": np.ones(len(dates),bool), "development": dates < pd.Timestamp("2026-01-01"), "validation": dates >= pd.Timestamp("2026-01-01")}
    for horizon,y in labels.items():
        valid = score.notna() & y.notna()
        xrank = score.where(valid).rank(axis=1, pct=True)
        yrank = y.where(valid).rank(axis=1, pct=True)
        counts = valid.sum(axis=1)
        ic = xrank.corrwith(yrank, axis=1).where(counts >= min_cross)
        # 并列因子值不按代码硬拆，部分二值或离散因子可能缺少某些组。
        group = np.ceil(xrank*5).clip(1,5)
        means = {q:y.where(group==q).mean(axis=1).where(counts>=min_cross) for q in range(1,6)}
        market = y.where(valid).mean(axis=1).where(counts>=min_cross)
        coverage = valid.sum(axis=1)/score.notna().sum(axis=1).replace(0,np.nan)
        for period,mask in periods.items():
            i = ic.loc[mask].dropna()
            row = dict(factor=factor,horizon=horizon,period=period,dates=len(i),rank_ic=i.mean(),ic_ir=i.mean()/i.std() if i.std()>0 else np.nan,label_coverage=coverage.loc[mask].mean(),observations=int(valid.loc[mask].sum().sum()))
            for q in range(1,6): row[f"q{q}"] = means[q].loc[mask].mean()
            row["q5_minus_q1"] = (means[5]-means[1]).loc[mask].mean()
            row["q5_minus_universe"] = (means[5]-market).loc[mask].mean()
            rows.append(row)
        for t in dates:
            daily.append(dict(date=t,factor=factor,horizon=horizon,rank_ic=ic.loc[t],q1=means[1].loc[t],q5=means[5].loc[t],universe=market.loc[t],coverage=coverage.loc[t]))
    return rows,daily


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="生成工作台因子研究数据")
    parser.add_argument("--data")
    args=parser.parse_args()
    settings=json.loads((ROOT/"configs/study.json").read_text(encoding="utf-8"))
    data={k:v.loc["2024-07-01":settings["end"]] for k,v in load_data(data_directory(args.data)).items()}
    library=FactorLibrary(data)
    dates=library.c.index
    sample=dates[(dates>=settings["start"])&(dates<=settings["end"])][::5]
    eligible=(data["close"].notna().cumsum()>=60).loc[sample] & (data["amt"].loc[sample]>0)
    labels={h:(library.o.shift(-h-1)/library.o.shift(-1)-1).loc[sample] for h in (5,10,20)}
    summaries=[]
    dailies=[]
    for name in settings["strategies"]:
        rows,daily=evaluate(library.get(name).loc[sample],labels,eligible,name,sample)
        summaries.extend(rows)
        dailies.extend(daily)
        print(f"因子统计完成：{name}",flush=True)
    output=ROOT/"artifacts/research"
    output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(summaries).to_csv(output/"factor_summary.csv",index=False,encoding="utf-8")
    pd.DataFrame(dailies).to_csv(output/"factor_daily.csv",index=False,encoding="utf-8")
    (output/"config.json").write_text(json.dumps(dict(start=settings["start"],end=settings["end"],step=5,horizons=[5,10,20],label="open[t+h+1]/open[t+1]-1",costs_included=False),indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
