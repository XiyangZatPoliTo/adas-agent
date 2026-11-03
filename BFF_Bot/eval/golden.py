"""黄金用例评估:对"已知答案"的案例批量运行分析流水线,统计结论是否正确。
Golden-case evaluation: run the analysis pipeline on cases with known answers.
试点时只需把 golden.csv 换成真实历史案例(并指向真实日志目录),就能度量真实表现。
"""


def evaluate_golden(rows: list[dict], analyze_fn) -> dict:
    """rows 来自 golden.csv;analyze_fn(log_file, note_time) 返回证据包。"""
    hit = {"verdict": 0, "dtc": 0, "funcs": 0}
    failures = []
    for r in rows:
        ev = analyze_fn(r["log_file"], r["note_time"])
        f = next((x for x in ev.get("findings", []) if x.get("dtc")), None)
        got = {"verdict": ev.get("verdict", "error"), "dtc": f["dtc"] if f else "",
               "funcs": ";".join(f["degraded_functions"]) if f else ""}
        exp = {"verdict": r["expected_verdict"], "dtc": r["expected_dtc"],
               "funcs": ";".join(sorted(x for x in r["expected_funcs"].split(";") if x))}
        for key in hit:
            hit[key] += got[key] == exp[key]
        if got != exp:
            failures.append({"row": r["log_file"], "expected": exp, "got": got})
    n = len(rows) or 1
    return {"n": len(rows), "verdict_acc": hit["verdict"] / n, "dtc_acc": hit["dtc"] / n,
            "funcs_acc": hit["funcs"] / n, "failures": failures}