import pandas as pd
import pytest

from BFF_Bot.analysis.templates import to_template
from BFF_Bot.analysis.window import extract_window, find_novel_templates
from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from scripts.generate_sample_log import CASES, build_case, fmt


def load_case(tmp_path, name):
    p = tmp_path / f"{name}.csv"
    build_case(CASES[name]).to_csv(p, index=False, encoding="utf-8")
    return load_dlt_csv(p), CASES[name]


def test_template_masks_numbers_but_keeps_codes():
    assert to_template("Alive : app = ctl , cycle = 53001 , events = 0") == "Alive : app = ctl , cycle = <N> , events = <N>"
    assert to_template("$XIMU,100,-0.011,9.8") == "$XIMU,<N>,<N>,<N>"
    assert to_template("EventID: 12 | trace - 7 | 24 54 52 49 b2 d0") == "EventID: <N> | trace - <N> | <HEXDUMP>"
    # 故障码必须原样保留,否则不同故障会被合并成同一个模板
    s = "Diag : DTC set , code = C1A01 , status = confirmed"
    assert to_template(s) == s


def test_window_requires_wall_time(tmp_path):
    df, cfg = load_case(tmp_path, "case_01_radar_comm_loss")
    df["wall_time"] = pd.NaT
    with pytest.raises(ValueError):
        extract_window(df, fmt(cfg["note_ms"]))


def test_novelty_finds_fault_chain_and_ignores_routine(tmp_path):
    df, cfg = load_case(tmp_path, "case_01_radar_comm_loss")
    novel, meta = find_novel_templates(df, fmt(cfg["note_ms"]))
    joined = " || ".join(novel["example"])
    assert "CommLost" in joined and "DTC set , code = C1A01" in joined and "Degrade" in joined
    assert "brightness" in joined                 # 干扰项也是"新"的,后续要靠因果规则排序
    assert "Cam : image status = OK" not in joined  # 例行消息不应被当成新事件
    assert meta["baseline_ok"] is True


def test_driver_cancel_has_no_dtc(tmp_path):
    df, cfg = load_case(tmp_path, "case_04_driver_cancel_acc")
    novel, _ = find_novel_templates(df, fmt(cfg["note_ms"]))
    joined = " || ".join(novel["example"])
    assert "driver_request" in joined and "DTC set" not in joined


def test_short_baseline_is_flagged(tmp_path):
    df, cfg = load_case(tmp_path, "case_03_camera_calib_error")  # 故障发生在日志开头
    _, meta = find_novel_templates(df, fmt(cfg["note_ms"]))
    assert meta["baseline_ok"] is False