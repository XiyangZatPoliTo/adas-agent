from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from scripts.generate_sample_log import CASES, build_case


def test_generated_log_loads_cleanly(tmp_path):
    out = build_case(CASES["case_01_radar_comm_loss"])
    p = tmp_path / "g.csv"
    out.to_csv(p, index=False, encoding="utf-8")
    df = load_dlt_csv(p)
    assert len(df) == len(out)                                   # 不丢行
    assert df["parse_ok"].all()
    assert df["wall_time"].notna().all()                         # 生成的是完整 ISO 时间
    assert {"binary", "text", "control"} <= set(df["kind"])      # 三种载荷形态都有
    assert df["text"].str.contains("DTC set , code = C1A01").any()


def test_ecu_clocks_are_independent():
    out = build_case(CASES["case_01_radar_comm_loss"])
    ts = out[out["Timestamp"] > 0].groupby("Ecuid")["Timestamp"].min()
    # 三个 ECU 的计时器数量级不同,不能直接跨 ECU 比较 Timestamp
    assert ts["GWY1"] > 10_000 and ts["CTL1"] > 2_000 and ts["PRC1"] < 100