import pandas as pd
import pytest

from BFF_Bot.loaders.dlt_csv import load_dlt_csv

HEADER = "Index,Time,Timestamp,Count,Ecuid,Apid,Ctid,SessionId,Type,Subtype,Mode,#Args,Payload\n"
ROWS = [
    # 0: 二进制,完整时间
    '1,2026-01-15 14:00:00.123,51.4909,1,SRR1,APP1,CTX1,0,log,info,non-verbose,0,[18] ----t9----|04 00 00 00 74 39\n',
    # 1: 文本,Payload 里有逗号所以带引号
    '2,2026-01-15 14:00:00.200,2129.9871,2,IPNX,APP2,CTX2,0,log,warn,verbose,8,"Life : App: abc , cycle: 53106 , # of events: 0"\n',
    # 2: 控制响应,Timestamp 为 0
    '3,2026-01-15 14:00:00.300,0,3,IPNY,,,0,control,response,non-verbose,0,[ ok] 00 00 00 06\n',
    # 3: 坏行:时间被截断、Timestamp 不是数字
    '4,30:04.2,abc,4,IPNX,APP2,CTX2,0,log,info,verbose,1,hello\n',
]


def write_csv(tmp_path, rows=ROWS, header=HEADER):
    p = tmp_path / "t.csv"
    p.write_text(header + "".join(rows), encoding="utf-8")
    return p


def test_kind_and_fields(tmp_path):
    df = load_dlt_csv(write_csv(tmp_path))
    assert list(df["kind"]) == ["binary", "text", "control", "text"]
    assert df.loc[0, "msg_id"] == 18
    assert df.loc[0, "payload_hex"] == "04 00 00 00 74 39"
    assert "cycle: 53106" in df.loc[1, "text"]


def test_zero_timestamp_is_missing(tmp_path):
    df = load_dlt_csv(write_csv(tmp_path))
    assert df.loc[0, "ecu_ts"] == pytest.approx(51.4909)
    assert pd.isna(df.loc[2, "ecu_ts"])  # 0 -> 缺失


def test_wall_time_full_vs_truncated(tmp_path):
    df = load_dlt_csv(write_csv(tmp_path))
    assert df.loc[0, "wall_time"] == pd.Timestamp("2026-01-15 14:00:00.123")
    assert pd.isna(df.loc[3, "wall_time"])  # 被截断的时间不瞎猜


def test_bad_row_is_kept_not_dropped(tmp_path):
    df = load_dlt_csv(write_csv(tmp_path))
    assert len(df) == 4  # 不丢行
    assert list(df["parse_ok"]) == [True, True, True, False]


def test_missing_column_raises(tmp_path):
    with pytest.raises(ValueError):
        load_dlt_csv(write_csv(tmp_path, rows=[], header="Index,Time\n"))