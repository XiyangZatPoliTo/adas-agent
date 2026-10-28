import json

import pandas as pd

from BFF_Bot.analysis.chains import build_findings
from BFF_Bot.analysis.events import COLUMNS
from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from scripts.generate_sample_log import CASES, build_case, fmt


def run(tmp_path, name):
    p = tmp_path / f"{name}.csv"
    build_case(CASES[name]).to_csv(p, index=False, encoding="utf-8")
    return analyze_window(load_dlt_csv(p), fmt(CASES[name]["note_ms"]))


# ---- 手工构造事件,用来测试边界情况 ----
def make_events(rows):
    recs = [dict(src_row=i, wall_time=pd.Timestamp(t), ecu="E1", app="", ctx="", level="info",
                 text=f"{cat} {fields}", category=cat, fields=fields, abnormal=ab)
            for i, (t, cat, fields, ab) in enumerate(rows)]
    return pd.DataFrame(recs, columns=COLUMNS)


def sensor(t, s="Rdr"):
    return (t, "sensor_status", {"sensor": s, "status": "CommLost"}, True)


def dtc(t, code="C1A01"):
    return (t, "dtc_set", {"code": code, "dtc_status": "confirmed"}, False)


def degrade(t, func="Acc", code="C1A01"):
    return (t, "function_state", {"func": func, "state": "Degrade", "reason": f"DTC_{code}"}, False)


# ---- 端到端场景 ----
def test_case01_fault_chain(tmp_path):
    r = run(tmp_path, "case_01_radar_comm_loss")
    json.dumps(r)  # 必须可序列化:它要交给 LLM 和 API
    f = r["findings"][0]
    assert r["verdict"] == "fault_chain" and r["confidence"] == "high"
    assert f["dtc"] == "C1A01" and f["degraded_functions"] == ["ACC", "AEB"]
    assert f["sensor_evidence"] == ["Rdr"] and f["consistent_with_dtc_table"] is True
    assert [e["role"] for e in f["evidence"]] == ["sensor_abnormal", "dtc_set", "function_degrade", "function_degrade"]
    assert any("brightness" in u["example"] for u in r["unclassified_novel"])  # 干扰项没有混进证据链


def test_case02_table_lists_more_functions_than_log(tmp_path):
    r = run(tmp_path, "case_02_camera_blocked")
    f = r["findings"][0]
    assert f["dtc"] == "C1A02" and f["degraded_functions"] == ["AEB", "LKA"]
    assert f["sensor_evidence"] == ["Cam"] and r["confidence"] == "high"
    # 表里还列了 LDW 但日志里没有:仅提示,不扣分
    assert f["consistent_with_dtc_table"] is True and "LDW" in f["unobserved_functions"]


def test_case03_short_baseline_noted(tmp_path):
    r = run(tmp_path, "case_03_camera_calib_error")
    assert r["findings"][0]["dtc"] == "C1A03"
    assert any("基线" in n for n in r["notes"])


def test_case04_driver_action_needs_human_confirmation(tmp_path):
    r = run(tmp_path, "case_04_driver_cancel_acc")
    assert r["verdict"] == "driver_action" and r["findings"] == []
    d = r["driver_findings"][0]
    assert d["function"] == "ACC" and d["needs_human_confirmation"] is True and d["confidence"] == "high"


# ---- 边界情况 ----
def test_missing_dtc_event_is_low_confidence():
    r = build_findings(make_events([degrade("2026-01-15 14:00:10")]))
    assert r["verdict"] == "fault_chain" and r["confidence"] == "low"


def test_dtc_after_degrade_is_flagged():
    r = build_findings(make_events([degrade("2026-01-15 14:00:09"), dtc("2026-01-15 14:00:10")]))
    f = r["findings"][0]
    assert f["confidence"] == "low" and any("之后才置位" in s for s in f["reasoning"])


def test_two_sensors_cap_confidence_at_medium():
    r = build_findings(make_events([
        sensor("2026-01-15 14:00:00.000", "Rdr"), sensor("2026-01-15 14:00:00.100", "Cam"),
        dtc("2026-01-15 14:00:00.500"), degrade("2026-01-15 14:00:00.650")]))
    assert r["confidence"] == "medium"


def test_no_events_is_inconclusive():
    r = build_findings(make_events([]))
    assert r["verdict"] == "inconclusive" and r["findings"] == []