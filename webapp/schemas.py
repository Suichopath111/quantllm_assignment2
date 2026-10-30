"""工作台请求模型。"""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Parameters(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    initial_cash: float=Field(1_000_000,ge=100,le=1e12)
    rebalance: int=Field(5,ge=1,le=250)
    top_n: int=Field(50,ge=1,le=5451)
    min_history: int=Field(60,ge=1,le=2000)
    commission: float=Field(.0003,ge=0,le=.05)
    min_commission: float=Field(5,ge=0,le=10000)
    slippage: float=Field(.001,ge=0,le=.1)
    participation: float=Field(.01,gt=0,le=1)
    stale_days: int=Field(60,ge=1,le=2000)
    stale_policy: Literal["writeoff","carry"]="writeoff"
    start: date=date(2025,1,1)
    end: date=date(2026,9,30)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.end < self.start: raise ValueError("结束日期必须不早于开始日期")
        return self


class RunRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field("",max_length=80)
    strategy: str="low_vol_momentum"
    config: Parameters=Field(default_factory=Parameters)
