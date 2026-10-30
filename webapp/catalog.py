"""策略中文名称与分组。"""
from factors import FactorLibrary

LABELS = {
    "low_vol_momentum": ("低波动 + 动量", "组合", "20日低波动与跳过最近5日的60日动量，各占一半排名权重。"),
    "high52": ("52周高点接近度", "高点与突破", "当前复权收盘价相对于过去250日及当日最高收盘价。"),
    "history_high": ("可见历史高点", "高点与突破", "2020年以来可见历史高点，不是上市以来高点。"),
    "body": ("K线实体", "K线结构", "日内实体收益，高分为阳线。"),
    "upper_shadow": ("短上影线", "K线结构", "负的上影线长度，高分为上影较短。"),
    "lower_shadow": ("长下影线", "K线结构", "下影线相对于开盘价的长度。"),
    "range": ("日内振幅", "K线结构", "最高价与最低价差相对于前收盘价。"),
    "clv": ("收盘位置 CLV", "K线结构", "接近1表示收盘靠近最高价，接近-1表示靠近最低价。"),
    "range_clv": ("高振幅 · 高位收盘", "K线结构", "振幅与CLV相乘。"),
    "range_low_close": ("高振幅 · 低位收盘", "K线结构", "负的振幅与CLV乘积。"),
    "small_body_range": ("小实体 · 大振幅", "K线结构", "振幅减去实体绝对收益。"),
    "up_streak": ("连续阳线", "K线结构", "连续阳线天数，缺失或十字星中断。"),
    "down_streak": ("连续阴线", "K线结构", "连续阴线天数，缺失或十字星中断。"),
    "low_vol20": ("20日低波动", "波动率", "负的20日日收益标准差。"),
    "low_parkinson20": ("低 Parkinson 波动", "波动率", "根据日内高低价计算的20日低波动。"),
    "vol_ratio": ("短长波动比", "波动率", "5日波动率 / 60日波动率。"),
    "vol_expansion": ("波动率扩张", "波动率", "5日波动率 / 5日前的60日波动率。"),
    "contraction_momentum": ("波动收缩 + 动量", "组合", "波动收缩与20日动量的同日组合。"),
    "gap": ("隔夜跳空", "隔夜与日内", "复权开盘价相对于前收盘价的收益。"),
    "on20": ("20日隔夜强度", "隔夜与日内", "最近20日隔夜简单收益之和。"),
    "id20": ("20日日内强度", "隔夜与日内", "最近20日日内简单收益之和。"),
    "on_minus_id": ("隔夜 − 日内", "隔夜与日内", "20日隔夜强度减去日内强度。"),
    "on_up_id_down": ("隔夜涨 · 日内跌", "隔夜与日内", "限定隔夜正、日内负的股票，按二者差排序。"),
    "on_down_id_up": ("隔夜跌 · 日内涨", "隔夜与日内", "限定隔夜负、日内正的股票，按日内减隔夜排序。"),
    "illiquidity20": ("Amihud 非流动性", "流动性", "20日绝对收益除以成交额的均值，高分为不流动。"),
    "liquidity20": ("20日成交额", "流动性", "20日平均成交额的对数。"),
    "amount_surge": ("成交额异常", "流动性", "当日成交额 / 此前20日平均成交额。"),
    "price_amount_divergence": ("价额背离", "流动性", "价格动量排名减去成交额变化排名。"),
    "volume_breakout": ("放额突破", "组合", "60日突破与成交额异常排名相加，非真实成交量。"),
    "quiet_rally": ("缩额上涨", "组合", "5日动量与低成交额异常排名相加。"),
}


def strategies():
    rows = []
    for name in FactorLibrary.names():
        if name.startswith("mom_"):
            parts = name.split("_")
            skip = len(parts) > 2
            label = f"{parts[1]}日动量" + (" · 跳过5日" if skip else "")
            group = "动量"
            description = "使用复权价格计算收益，高分优先。" + ("剔除最近5日收益。" if skip else "")
        elif name.startswith("breakout_"):
            label, group, description = f"{name.split('_')[1]}日突破", "高点与突破", "收盘价 / 此前窗口最高价，排除当日高点。"
        else:
            label, group, description = LABELS[name]
        rows.append(dict(id=name, name=label, group=group, description=description))
    return rows
