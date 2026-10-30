"""本地研究工作台API：任务、结果、行情目录与因子研究。"""
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Literal
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from quantlab.engine import Config
from quantlab.paths import ROOT, data_directory, state_directory
from .catalog import strategies
from .jobs import JobManager, JobStore
from .schemas import RunRequest

BASE=ROOT
STATIC=Path(__file__).with_name("static")
TABLES={"equity","trades","positions","events"}


def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,np.generic): return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value


@lru_cache(maxsize=24)
def cached_csv(path, modified, size):
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def frame(path):
    path=Path(path)
    if not path.exists(): return pd.DataFrame()
    stat=path.stat()
    return cached_csv(str(path),stat.st_mtime_ns,stat.st_size)




def create_app(data_dir=None, state_dir=None, import_existing=True):
    data_dir=data_directory(data_dir)
    store=JobStore(state_directory(state_dir))
    manager=JobManager(store,data_dir)
    catalog=strategies()
    by_id={r["id"]:r for r in catalog}

    @asynccontextmanager
    async def lifespan(app):
        store.interrupt_unfinished()
        if import_existing:
            for request in sorted((BASE/"artifacts/runs").glob("*/request.json")):
                folder=request.parent
                payload=json.loads(request.read_text(encoding="utf-8"))
                if (folder/"summary.json").is_file():
                    store.add("study-"+folder.name,payload["name"],payload["strategy"],payload["config"],folder,"completed")
        yield
        manager.close()

    app=FastAPI(title="QuantLab 本地回测工作台",version="1.0.0",lifespan=lifespan)
    app.state.store=store
    app.state.manager=manager

    @app.middleware("http")
    async def local_request(request, call_next):
        # 限制跨站写请求，避免其他网页向本机服务提交任务。
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin=request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail":"不接受跨站写请求"},status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

    def find(identifier,completed=False):
        row=store.get(identifier)
        if row is None: raise HTTPException(404,"回测不存在")
        if completed and row["status"]!="completed": raise HTTPException(409,"回测尚未完成")
        return row

    def public(row):
        result={k:v for k,v in row.items() if k!="folder"}
        result["strategy_name"]=by_id.get(row["strategy"],{}).get("name",row["strategy"])
        result["imported"]=row["id"].startswith("example-")
        result["progress"]=1 if row["status"]=="completed" else 0
        progress=Path(row["folder"])/"progress.json"
        if progress.exists() and row["status"]!="completed":
            try: result.update(json.loads(progress.read_text(encoding="utf-8")))
            except (OSError,ValueError): pass
        if row["status"]=="completed":
            summary=Path(row["folder"])/"summary.json"
            if summary.exists(): result["summary"]=json.loads(summary.read_text(encoding="utf-8"))
        return clean(result)

    @lru_cache(maxsize=1)
    def dataset():
        path=data_dir/"close.feather"
        if not path.exists(): raise HTTPException(503,"未找到feathers/close.feather")
        dates=pd.read_feather(path,columns=["date"])["date"]
        with pa.memory_map(str(path),"r") as source:
            names=ipc.open_file(source).schema.names
        symbols=[s for s in names if s.endswith((".SZ",".SH"))]
        files=[dict(name=p.name,size=p.stat().st_size) for p in sorted(data_dir.glob("*.feather"))]
        return dict(start=str(dates.min().date()),end=str(dates.max().date()),sessions=len(dates),stocks=len(symbols),sz=sum(s.endswith(".SZ") for s in symbols),sh=sum(s.endswith(".SH") for s in symbols),files=files,fields=["开盘价","收盘价","最高价","最低价","累计复权因子","成交额","成交笔数"],unavailable=["真实成交量与换手率","历史ST状态与官方逐日涨跌停价","企业行为明细与完整退市清偿信息"],assumptions=["日频开盘撮合；停牌、涨跌停与容量约束采用既有模型", "累计复权因子变化按总收益等价持股记账", "连续缺失行情按配置执行减值或最后价格估值"])

    @app.get("/api/health")
    def health(): return {"status":"ok","engine":"local","version":"1.0.0"}

    @app.get("/api/data")
    def data(): return dataset()

    @app.get("/api/strategies")
    def get_strategies(): return {"items":catalog,"defaults":asdict(Config())}

    @app.get("/api/runs")
    def runs(): return {"items":[public(row) for row in store.list()]}

    @app.post("/api/runs",status_code=202)
    def submit(request: RunRequest):
        if request.strategy not in by_id: raise HTTPException(422,"未知策略")
        info=dataset()
        config=request.config.model_dump(mode="json")
        if config["start"]<info["start"] or config["end"]>info["end"]:
            raise HTTPException(422,f"日期必须位于 {info['start']} 至 {info['end']} 内")
        if config["top_n"]>info["stocks"]: raise HTTPException(422,"持仓数超出数据股票数")
        dates=pd.read_feather(data_dir/"close.feather",columns=["date"])["date"]
        if not ((dates>=pd.Timestamp(config["start"]))&(dates<=pd.Timestamp(config["end"]))).any():
            raise HTTPException(422,"区间内没有交易日")
        payload={"name":request.name.strip() or by_id[request.strategy]["name"],"strategy":request.strategy,"config":config}
        try: return public(manager.submit(payload))
        except ValueError as exc: raise HTTPException(429,str(exc)) from exc

    @app.get("/api/runs/{identifier}")
    def detail(identifier: str): return public(find(identifier))

    @app.post("/api/runs/{identifier}/cancel")
    def cancel(identifier: str):
        find(identifier)
        try: manager.cancel(identifier)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc
        return public(find(identifier))

    @app.get("/api/runs/{identifier}/curve")
    def curve(identifier: str):
        row=find(identifier,True)
        table=frame(Path(row["folder"])/"equity.csv")
        if table.empty: raise HTTPException(404,"净值文件不存在")
        return {"items":clean(table.to_dict("records"))}

    @app.get("/api/runs/{identifier}/performance")
    def performance(identifier: str):
        row=find(identifier,True)
        table=frame(Path(row["folder"])/"equity.csv").copy()
        if table.empty: raise HTTPException(404,"净值文件不存在")
        table["date"]=pd.to_datetime(table["date"])
        initial=row["config"]["initial_cash"]
        result={}
        for kind,freq in (("annual","Y"),("monthly","M")):
            ends=table.groupby(table["date"].dt.to_period(freq),sort=True)["equity"].last()
            previous=ends.shift(1).fillna(initial)
            result[kind]=[dict(period=str(period),return_value=float(value)) for period,value in (ends/previous-1).items()]
        return clean(result)

    @app.get("/api/runs/{identifier}/tables/{table}")
    def table_data(identifier: str,table: Literal["trades","positions","events"],page: int=Query(1,ge=1),page_size: int=Query(20,ge=1,le=200),search: str=Query("",max_length=50),side: Literal["all","buy","sell"]="all"):
        row=find(identifier,True)
        table_frame=frame(Path(row["folder"])/f"{table}.csv")
        if search and "symbol" in table_frame:
            table_frame=table_frame[table_frame.symbol.astype(str).str.contains(search,case=False,regex=False)]
        if side!="all" and "side" in table_frame: table_frame=table_frame[table_frame.side==side]
        if "date" in table_frame: table_frame=table_frame.sort_values("date",ascending=False,kind="stable")
        return {"items":clean(table_frame.iloc[(page-1)*page_size:page*page_size].to_dict("records")),"total":len(table_frame),"page":page,"page_size":page_size}

    @app.get("/api/runs/{identifier}/download/{filename}")
    def download(identifier: str,filename: Literal["summary.json","equity.csv","trades.csv","positions.csv","events.csv","equity.png"]):
        row=find(identifier,True)
        path=Path(row["folder"])/filename
        if not path.is_file(): raise HTTPException(404,"文件不存在")
        return FileResponse(path,filename=f"{identifier}-{filename}")

    @app.get("/api/research")
    def research(horizon: Literal["5","10","20"]="5",period: Literal["all","development","validation"]="validation"):
        table=frame(BASE/"artifacts/research/factor_summary.csv")
        if table.empty: return {"items":[],"available":False}
        selection=table[(table.horizon==int(horizon))&(table.period==period)]
        return {"items":clean(selection.to_dict("records")),"available":True,"sample_step":5,"costs_included":False}

    @app.get("/api/research/{factor}")
    def research_detail(factor: str,horizon: Literal["5","10","20"]="5"):
        if factor not in by_id: raise HTTPException(404,"因子不存在")
        table=frame(BASE/"artifacts/research/factor_daily.csv")
        if table.empty: return {"items":[]}
        selection=table[(table.factor==factor)&(table.horizon==int(horizon))]
        return {"items":clean(selection.to_dict("records"))}

    @app.get("/api/conditions")
    def conditions(study: str="gap_bins",period: Literal["all","development","validation"]="all"):
        table=frame(BASE/"artifacts/research/conditional_returns.csv")
        if table.empty: return {"items":[]}
        return {"items":clean(table[(table.study==study)&(table.period==period)].to_dict("records"))}

    @app.get("/")
    def index(): return FileResponse(STATIC/"index.html")

    app.mount("/assets",StaticFiles(directory=STATIC),name="assets")
    return app
