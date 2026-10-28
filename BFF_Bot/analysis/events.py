"""用规则从文本消息里抽取结构化事件。
Extract structured events from text messages using configurable rules.
"""
from pathlib import Path

import pandas as pd
import yaml

RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.yaml"
COLUMNS = ["src_row", "wall_time", "ecu", "app", "ctx", "level", "text", "category", "fields", "abnormal"]


def load_rules(path=RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def extract_events(df: pd.DataFrame, rules: dict = None) -> pd.DataFrame:
    """返回被规则识别的事件。没被任何规则命中的行不在这里,由调用方另行处理(不丢弃,不猜测)。"""
    rules = rules or load_rules()
    txt = df[df["kind"] == "text"]  # 二进制消息读不懂,不参与
    parts = []
    for category, spec in rules.items():
        for pattern in spec["patterns"]:
            # str.extract:正则里的命名分组自动变成列。没命中的行整行是 NaN。
            m = txt["text"].str.extract(pattern)
            hit = m.notna().all(axis=1)
            if not hit.any():
                continue
            recs = m[hit].to_dict("records")  # 每个事件的字段字典
            part = txt.loc[hit, ["src_row", "wall_time", "ecu", "app", "ctx", "level", "text"]].copy()
            part["category"] = category
            part["fields"] = recs
            # 异常标记:规则里声明了"某字段取值不在正常列表里",就算异常
            nf, nv = spec.get("normal_field"), spec.get("normal_values", [])
            part["abnormal"] = [bool(nf) and r.get(nf) not in nv for r in recs]
            parts.append(part)
    if not parts:
        return pd.DataFrame(columns=COLUMNS)  # 空结果也保持列结构,下游不用特判
    return (pd.concat(parts).sort_values(["wall_time", "src_row"]).reset_index(drop=True))[COLUMNS]