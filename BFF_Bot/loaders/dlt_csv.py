"""DLT 导出 CSV 的加载层:把杂乱的原始 CSV 标准化成统一结构。
Loader for DLT-exported CSV: normalizes raw, messy rows into one standard schema.
原则:不丢行、不崩溃、不假装读懂(宁可标记 parse_ok=False,也不悄悄丢弃或猜测)。
"""
import re

import pandas as pd

# 必需的原始列。真实导出的列名变了,只需改这里,下游代码不用动。
REQUIRED_COLUMNS = ["Time", "Timestamp", "Ecuid", "Apid", "Ctid", "Type", "Subtype", "Mode", "Payload"]

_HAS_DATE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")  # 含"年月日"部分,才算完整时间
_MSG_ID = re.compile(r"^\[\s*(\d+)\]")                       # "[18] ..." 里的 18
_HEX_TAIL = re.compile(r"(?:[0-9a-fA-F]{2}\s?)+")


def payload_kind(p: str) -> str:
    """把 Payload 粗分为 empty / control / binary / text 四类。"""
    if p == "":
        return "empty"
    if re.match(r"^\[\s*[A-Za-z_]+\]", p):  # "[ ok] 00 00 .."
        return "control"
    # 二进制:"[18] 乱码|04 00 .." —— 方括号里是数字 ID,最后一个 | 后面全是十六进制字节。
    # 同时检查"开头是 [数字]",是为了不把 "EventID: 7 | cost - 1 | 31 30 .." 这类文本误判成二进制。
    head, sep, tail = p.rpartition("|")
    if sep and re.match(r"^\[\s*\d+\]", head) and _HEX_TAIL.fullmatch(tail):
        return "binary"
    return "text"


def parse_wall_time(s: pd.Series, dayfirst: bool = False) -> pd.Series:
    """Time 列可能是完整日期时间,也可能是被 Excel 截断的 'mm:ss.f'。
    只有含日期部分才解析,否则一律 NaT。
    为什么不让 pandas 硬解析 '30:04.2'?它可能把残缺字符串"猜"成某个错误的时间,
    悄悄给出错误结果比明确的缺失更危险。
    """
    has_date = s.str.contains(_HAS_DATE)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    if has_date.any():
        # dayfirst 解决 "5/10/2026" 是 5 月 10 日还是 10 月 5 日的歧义。
        out[has_date] = pd.to_datetime(s[has_date], errors="coerce", dayfirst=dayfirst, format="mixed")
    return out


def load_dlt_csv(path, dayfirst: bool = False) -> pd.DataFrame:
    # 全部读成字符串、空值保留为 "":避免 pandas 偷偷转 NaN 或猜错列类型。
    raw = pd.read_csv(path, dtype=str, keep_default_na=False,
                      encoding="utf-8", encoding_errors="replace")

    # 快速失败:缺列就明确报错,比后面抛一个看不懂的 KeyError 好排查得多。
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV 缺少必需的列: {missing};实际列: {list(raw.columns)}")

    payload = raw["Payload"]
    kind = payload.map(payload_kind)
    ts = pd.to_numeric(raw["Timestamp"], errors="coerce")  # 转不动的变 NaN,不抛异常

    msg_id = pd.to_numeric(payload.str.extract(_MSG_ID)[0], errors="coerce").astype("Int64")
    tail = payload.str.rpartition("|")[2].str.strip()

    # parse_ok:不确定的行打上"不可信"标记,但绝不丢弃。后续分析工具可据此降低置信度。
    parse_ok = ts.notna() & (raw["Ecuid"] != "") & ~payload.str.contains("\ufffd", regex=False)

    return pd.DataFrame({
        "src_row": range(len(raw)),
        "wall_time": parse_wall_time(raw["Time"], dayfirst),
        # 各 ECU 计时器基准不同,0 表示"没有有效 ECU 时间戳",统一记为缺失。
        "ecu_ts": ts.where(ts > 0),
        "ecu": raw["Ecuid"], "app": raw["Apid"], "ctx": raw["Ctid"],
        "msg_type": raw["Type"], "level": raw["Subtype"], "mode": raw["Mode"],
        "kind": kind,
        "msg_id": msg_id.where(kind.isin(["binary", "control"])),
        "text": payload.where(kind == "text", ""),
        "payload_hex": tail.where(kind == "binary", ""),
        "raw_payload": payload,
        "parse_ok": parse_ok,
    })