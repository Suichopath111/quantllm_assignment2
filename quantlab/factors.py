"""纯历史 OHLC、复权因子、成交额因子；统一为分数越高越偏好。"""
import numpy as np
import pandas as pd


class FactorLibrary:
    def __init__(self, data):
        self.data = data
        self.c = data["close"].where(data["close"] > 0) * data["cumadj"].where(data["cumadj"] > 0)
        self.o = data["open"].where(data["open"] > 0) * data["cumadj"].where(data["cumadj"] > 0)
        self.h = data["high"].where(data["high"] > 0) * data["cumadj"].where(data["cumadj"] > 0)
        self.l = data["low"].where(data["low"] > 0) * data["cumadj"].where(data["cumadj"] > 0)
        self.r = self.c.pct_change(fill_method=None)
        self.amount = data["amt"].where(data["amt"] > 0)

    @staticmethod
    def names():
        return ([f"mom_{w}" for w in (5,10,20,60,120,250)]
                + [f"mom_{w}_skip5" for w in (10,20,60,120,250)]
                + ["high52", "history_high"]
                + [f"breakout_{w}" for w in (20,60,120,250)]
                + ["body", "upper_shadow", "lower_shadow", "range", "clv", "range_clv", "range_low_close", "small_body_range", "up_streak", "down_streak"]
                + ["low_vol20", "low_parkinson20", "vol_ratio", "vol_expansion", "contraction_momentum", "low_vol_momentum"]
                + ["gap", "on20", "id20", "on_minus_id", "on_up_id_down", "on_down_id_up"]
                + ["illiquidity20", "liquidity20", "amount_surge", "price_amount_divergence", "volume_breakout", "quiet_rally"])

    def momentum(self, w, skip=0):
        x = self.c.shift(skip) / self.c.shift(w) - 1
        return x.where(self.c.notna().rolling(w+1).sum() == w+1)

    def get(self, name):
        c,o,h,l,r,a = self.c,self.o,self.h,self.l,self.r,self.amount
        rank = lambda x: x.rank(axis=1, pct=True)
        vol = lambda w: r.rolling(w).std()
        # 按因子族按需计算，避免每个动量因子重复分配整组K线矩阵。
        if name in ("clv", "range_clv", "range_low_close"):
            spread = (h-l).where(h>l)
            clv = (2*c-h-l)/spread
        if name in ("range", "range_clv", "range_low_close", "small_body_range"):
            ran = (h-l)/c.shift(1)
        if name in ("body", "small_body_range"):
            body = (c-o)/o
        if name in ("amount_surge", "volume_breakout", "quiet_rally"):
            surge = a / a.shift(1).rolling(20).mean()
        if name.startswith("mom_"):
            parts = name.split("_")
            result = self.momentum(int(parts[1]), 5 if len(parts)>2 else 0)
        elif name == "high52": result = c / c.rolling(251).max()
        elif name == "history_high": result = c / c.expanding(min_periods=60).max()
        elif name.startswith("breakout_"): result = c / h.shift(1).rolling(int(name.split("_")[1])).max()
        elif name == "body": result = body
        elif name == "upper_shadow": result = -(h-np.maximum(o,c))/o
        elif name == "lower_shadow": result = (np.minimum(o,c)-l)/o
        elif name == "range": result = ran
        elif name == "clv": result = clv
        elif name == "range_clv": result = ran * clv
        elif name == "range_low_close": result = -ran * clv
        elif name == "small_body_range": result = ran - body.abs()
        elif name in ("up_streak", "down_streak"):
            # 连续阳线/阴线按日内实体判断，缺失或十字星中断。
            mask = ((c>o) if name == "up_streak" else (c<o)).to_numpy()
            streak = np.zeros(mask.shape, dtype=np.int16)
            for t in range(len(mask)):
                streak[t] = (streak[t-1]+1)*mask[t] if t else mask[t]
            result = pd.DataFrame(streak, index=c.index, columns=c.columns)
        elif name == "low_vol20": result = -vol(20)
        elif name == "low_parkinson20": result = -np.sqrt((np.log(h/l)**2).rolling(20).mean()/(4*np.log(2)))
        elif name == "vol_ratio": result = vol(5)/vol(60).replace(0,np.nan)
        elif name == "vol_expansion": result = vol(5)/vol(60).shift(5).replace(0,np.nan)
        elif name == "contraction_momentum": result = rank(-vol(5)/vol(60).replace(0,np.nan)) + rank(self.momentum(20))
        elif name == "low_vol_momentum": result = rank(-vol(20)) + rank(self.momentum(60,5))
        elif name == "gap": result = o/c.shift(1)-1
        elif name in ("on20", "id20", "on_minus_id", "on_up_id_down", "on_down_id_up"):
            on = (o/c.shift(1)-1).rolling(20).sum()
            intra = (c/o-1).rolling(20).sum()
            result = {"on20":on,"id20":intra,"on_minus_id":on-intra,"on_up_id_down":(on-intra).where((on>0)&(intra<0)),"on_down_id_up":(intra-on).where((on<0)&(intra>0))}[name]
        elif name == "illiquidity20": result = (r.abs()/a*1e8).rolling(20).mean()
        elif name == "liquidity20": result = np.log(a.rolling(20).mean())
        elif name == "amount_surge": result = surge
        elif name == "price_amount_divergence": result = rank(self.momentum(20))-rank(a/a.shift(20)-1)
        elif name == "volume_breakout": result = rank(self.get("breakout_60")) + rank(surge)
        elif name == "quiet_rally": result = rank(self.momentum(5)) + rank(-surge)
        else: raise KeyError(name)
        return result.where(c.notna() & o.notna() & h.notna() & l.notna() & a.notna()).replace([np.inf,-np.inf], np.nan)
