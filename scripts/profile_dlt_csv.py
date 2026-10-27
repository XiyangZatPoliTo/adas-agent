"""给 DLT 导出的 CSV 做"体检":先摸清结构、噪声、时间基准,再决定怎么解析。
Profile a DLT-exported CSV: understand structure, noise and clocks before parsing.
"""
import argparse
import re

import pandas as pd


def load_raw(path: str) -> pd.DataFrame:
    # 先全部读成字符串,空值保留为 "":避免 pandas 悄悄把空单元格变成 NaN、
    # 或把列类型猜错;encoding_errors="replace":遇到坏字节不崩溃。
    df = pd.read_csv(path, dtype=str, keep_default_na=False,
                     encoding="utf-8", encoding_errors="replace")
    # 再"有控制地"转数值:转不动的变 NaN,而不是整个程序报错。
    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
    return df


def payload_kind(p: str) -> str:
    """把 Payload 粗分为 empty / control / binary / text 四类。"""
    if p == "":
        return "empty"
    if re.match(r"^\[\s*[A-Za-z_]+\]", p):          # "[ ok] 00 00 .."
        return "control"
    # 二进制:"[18] 乱码|04 00 00 .." —— 方括号里是数字消息 ID,最后一个 | 后面全是十六进制字节。
    # 用 rpartition 而不是复杂正则,避免长字符串上的回溯问题。
    head, sep, tail = p.rpartition("|")
    if sep and re.match(r"^\[\s*\d+\]", head) and re.fullmatch(r"(?:[0-9a-fA-F]{2}\s?)+", tail):
        return "binary"
    return "text"  # verbose 文本,可以用规则解析


def to_template(msg: str) -> str:
    """把数字换成占位符,让"只有数字不同"的消息归为同一模板。
    这是日志模板挖掘(log template mining)的最简版。
    """
    msg = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", msg)
    return re.sub(r"\d+(?:\.\d+)?", "<N>", msg)


def main(path: str) -> None:
    df = load_raw(path)
    df["kind"] = df["Payload"].map(payload_kind)
    print(f"行数: {len(df)}\n列: {list(df.columns[:-1])}")

    # [1] 各 ECU 的计时器范围:如果范围差几个数量级,说明时钟不在同一基准上
    pos = df[df["Timestamp"] > 0]
    by = df.groupby("Ecuid")
    summary = pd.DataFrame({
        "rows": by.size(),
        "rows_ts0": by["Timestamp"].apply(lambda s: int((s == 0).sum())),
        "ts_min": pos.groupby("Ecuid")["Timestamp"].min(),
        "ts_max": pos.groupby("Ecuid")["Timestamp"].max(),
    })
    print("\n[1] 各 ECU 的 Timestamp 范围(rows_ts0 = Timestamp 为 0 的行数)")
    print(summary.to_string())

    # [2] Time 列的分辨率:取值越少,说明越粗
    print(f"\n[2] Time 列共有 {df['Time'].nunique()} 个不同取值,示例: {list(df['Time'].unique()[:5])}")

    # [3] 级别 x 模式,以及 Payload 形态占比
    print("\n[3] 级别(Subtype) x 模式(Mode)")
    print(pd.crosstab(df["Subtype"].replace("", "(none)"), df["Mode"]).to_string())
    print("\n    Payload 形态占比")
    print(df["kind"].value_counts().to_string())

    # [4] 文本消息 Top 模板:观察 error/warn 级别的消息是不是大量重复的常态噪声
    txt = df[df["kind"] == "text"].copy()
    txt["template"] = txt["Payload"].map(to_template)
    top = (txt.groupby(["Subtype", "template"]).size().reset_index(name="count")
              .sort_values("count", ascending=False).head(10))
    top["template"] = top["template"].str.slice(0, 90)  # 截断,避免刷屏
    print("\n[4] 文本消息 Top10 模板")
    print(top.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="DLT 导出的 CSV 路径")
    main(parser.parse_args().path)