from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from scripts.generate_sample_log import CASES, build_case, fmt


def test_case05_is_inconclusive_and_surfaces_unclassified_message(tmp_path):
    name = "case_05_insufficient_evidence"
    p = tmp_path / "c5.csv"
    build_case(CASES[name]).to_csv(p, index=False, encoding="utf-8")
    r = analyze_window(load_dlt_csv(p), fmt(CASES[name]["note_ms"]))
    assert r["verdict"] == "inconclusive" and r["confidence"] == "low"
    assert r["findings"] == [] and r["driver_findings"] == []
    assert any("reinit" in u["example"] for u in r["unclassified_novel"])  # 陌生消息被保留,没有丢弃
    assert r["notes"]  # 有"证据不足"的说明