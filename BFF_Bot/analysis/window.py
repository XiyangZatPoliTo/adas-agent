"""窗口提取与"新出现事件"发现。
Time-window extraction and novel-event discovery.
"""
import pandas as pd

from BFF_Bot.analysis.templates import to_template

BASELINE_MIN_S = 5.0  # 基线短于此秒数,新颖性结论的可信度低
# 同一个模板的身份 = 谁发的(ecu/app/ctx) + 级别 + 模板文本
KEYS = ["ecu", "app", "ctx", "level", "template"]


def _bounds(center, before_s, after_s):
    c = pd.Timestamp(center)
    return c - pd.Timedelta(seconds=before_s), c + pd.Timedelta(seconds=after_s)


def extract_window(df: pd.DataFrame, center, before_s: float = 12.0, after_s: float = 1.0) -> pd.DataFrame:
    """以 logbook 时间为中心取窗口。窗口向前更宽,因为测试员总是事后才记录。"""
    # 快速失败:没有挂钟时间就没法按 logbook 定位,明确告诉用户怎么修,而不是返回空结果。
    if df["wall_time"].isna().all():
        raise ValueError("日志中没有可用的挂钟时间(wall_time 全为空)。请用带完整日期时间的 CSV 重新导出。")
    lo, hi = _bounds(center, before_s, after_s)
    return df[df["wall_time"].between(lo, hi)]


def _with_template(d: pd.DataFrame) -> pd.DataFrame:
    # 只处理文本消息。二进制消息没有描述文件读不懂,不假装读懂。
    t = d[d["kind"] == "text"].copy()
    t["template"] = t["text"].map(to_template)
    return t


def find_novel_templates(df: pd.DataFrame, center, before_s: float = 12.0, after_s: float = 1.0):
    """返回 (新出现的模板表, 元信息)。"""
    win = extract_window(df, center, before_s, after_s)
    lo, hi = _bounds(center, before_s, after_s)
    base = df[df["wall_time"] < lo]  # 基线:窗口之前的全部内容

    wt, bt = _with_template(win), _with_template(base)
    seen = set(bt[KEYS].itertuples(index=False, name=None))

    g = (wt.groupby(KEYS)
           .agg(count=("text", "size"), first_time=("wall_time", "min"),
                first_row=("src_row", "min"), example=("text", "first"))
           .reset_index())
    # 用布尔 Series 过滤:列表为空时直接 g[[]] 会被 pandas 当成"选择零列",是个经典坑
    is_new = pd.Series([tuple(r) not in seen for r in g[KEYS].itertuples(index=False, name=None)],
                       index=g.index, dtype=bool)
    # 排序:先按到达时间;同一批次(Time 相同)用文件行序打破平局
    novel = g[is_new].sort_values(["first_time", "first_row"]).reset_index(drop=True)

    baseline_seconds = max((lo - df["wall_time"].min()).total_seconds(), 0.0)
    meta = dict(window_start=lo, window_end=hi, rows_in_window=len(win),
                baseline_seconds=baseline_seconds, baseline_ok=baseline_seconds >= BASELINE_MIN_S)
    return novel, meta