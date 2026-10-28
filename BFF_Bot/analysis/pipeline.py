"""分析流水线:窗口 -> 新颖性 -> 事件抽取 -> 因果链。输出可直接 JSON 序列化。
Analysis pipeline: window -> novelty -> events -> causal chain. Output is JSON-serializable.
"""
from BFF_Bot.analysis.chains import build_findings
from BFF_Bot.analysis.events import extract_events
from BFF_Bot.analysis.window import extract_window, find_novel_templates


def _ts(t) -> str:
    return t.strftime("%H:%M:%S.%f")[:-3]


def analyze_window(df, center, before_s: float = 12.0, after_s: float = 1.0) -> dict:
    novel, meta = find_novel_templates(df, center, before_s, after_s)
    events = extract_events(extract_window(df, center, before_s, after_s))
    result = build_findings(events, baseline_ok=meta["baseline_ok"])

    # 新出现但没被规则识别的模板:不丢弃,原样交给后面的 LLM 或人工(规则管确定的,LLM 管不确定的)
    matched = set(events["text"])
    unclassified = novel[~novel["example"].isin(matched)] if not novel.empty else novel
    result["unclassified_novel"] = [
        dict(ecu=r["ecu"], level=r["level"], count=int(r["count"]), example=r["example"])
        for r in unclassified.to_dict("records")]
    result["window"] = dict(start=_ts(meta["window_start"]), end=_ts(meta["window_end"]),
                            rows=int(meta["rows_in_window"]),
                            baseline_seconds=round(float(meta["baseline_seconds"]), 1))
    return result