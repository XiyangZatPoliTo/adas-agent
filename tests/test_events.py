import pandas as pd

from BFF_Bot.analysis.events import COLUMNS, extract_events
from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from scripts.generate_sample_log import CASES, build_case


def load_case(tmp_path, name):
    p = tmp_path / f"{name}.csv"
    build_case(CASES[name]).to_csv(p, index=False, encoding="utf-8")
    return load_dlt_csv(p)


def test_fault_chain_events_are_structured(tmp_path):
    ev = extract_events(load_case(tmp_path, "case_01_radar_comm_loss"))
    assert {"sensor_status", "dtc_set", "function_state"} <= set(ev["category"])
    dtc = ev[ev["category"] == "dtc_set"].iloc[0]["fields"]
    assert dtc["code"] == "C1A01"
    degraded = {f["func"] for f in ev[ev["category"] == "function_state"]["fields"] if f["state"] == "Degrade"}
    assert degraded == {"Acc", "Aeb"}  # 两种不同措辞风格的消息都被识别
    # 只有雷达的状态异常;摄像头全程正常
    bad = {f["sensor"] for f, a in zip(ev["fields"], ev["abnormal"]) if a}
    assert bad == {"Rdr"}


def test_driver_cancel_events(tmp_path):
    ev = extract_events(load_case(tmp_path, "case_04_driver_cancel_acc"))
    assert "dtc_set" not in set(ev["category"])
    assert ev[ev["category"] == "driver_action"].iloc[0]["fields"]["button"] == "ACC_cancel"
    state = ev[ev["category"] == "function_state"].iloc[0]["fields"]
    assert state["state"] == "Deactivate" and state["reason"] == "driver_request"


def test_unmatched_messages_are_not_events(tmp_path):
    ev = extract_events(load_case(tmp_path, "case_01_radar_comm_loss"))
    assert not ev["text"].str.contains("brightness").any()  # 干扰项没有对应规则,不会被当成事件


def test_empty_input_keeps_columns(tmp_path):
    df = load_case(tmp_path, "case_01_radar_comm_loss")
    ev = extract_events(df.iloc[0:0])
    assert ev.empty and list(ev.columns) == COLUMNS