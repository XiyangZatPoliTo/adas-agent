"""端到端演示:logbook 时间 -> 窗口 -> 新出现模板 -> 结构化事件。"""
import argparse
from pathlib import Path

import pandas as pd

from BFF_Bot.analysis.events import extract_events
from BFF_Bot.analysis.window import extract_window, find_novel_templates
from BFF_Bot.loaders.dlt_csv import load_dlt_csv

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"


def ts(t) -> str:
    return t.strftime("%H:%M:%S.%f")[:-3]  # 统一显示到毫秒


def main(case_file: str) -> None:
    logbook = pd.read_csv(LOG_DIR / "logbook.csv", dtype=str)
    entry = logbook[logbook["log_file"] == case_file].iloc[0]
    df = load_dlt_csv(LOG_DIR / case_file)
    novel, meta = find_novel_templates(df, entry["note_time"])

    print(f"测试员记录: {entry['note']}  (时间 {entry['note_time']})")
    print(f"窗口: {ts(meta['window_start'])} ~ {ts(meta['window_end'])},窗口内 {meta['rows_in_window']} 行,"
          f"基线 {meta['baseline_seconds']:.1f} 秒")
    if not meta["baseline_ok"]:
        print("提示: 基线过短,新颖性结论可信度较低")

    # 1) 窗口内新出现的模板(上一步的成果)
    print("\n[1] 窗口内新出现的消息模板")
    if novel.empty:
        print("  (无)")
    else:
        view = novel.assign(first_time=novel["first_time"].map(ts), example=novel["example"].str.slice(0, 70))
        print(view[["first_time", "ecu", "level", "count", "example"]].to_string(index=False))

    # 2) 用规则把窗口内的消息抽取成结构化事件
    events = extract_events(extract_window(df, entry["note_time"]))
    normal_sensor = (events["category"] == "sensor_status") & ~events["abnormal"]
    print(f"\n[2] 规则识别的事件(已隐藏 {int(normal_sensor.sum())} 条正常的传感器状态)")
    shown = events[~normal_sensor]
    if shown.empty:
        print("  (无)")
    else:
        print(shown.assign(wall_time=shown["wall_time"].map(ts))[
            ["wall_time", "ecu", "category", "abnormal", "fields"]].to_string(index=False))

    # 3) 新出现、但没被任何规则识别的模板:不丢弃,留给人工或 LLM 判断
    unclassified = novel[~novel["example"].isin(set(events["text"]))] if not novel.empty else novel
    print("\n[3] 新出现但未被规则识别的模板(供人工/LLM 参考)")
    if unclassified.empty:
        print("  (无)")
    else:
        print(unclassified[["ecu", "level", "count", "example"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_file", help="例如 case_01_radar_comm_loss.csv")
    main(parser.parse_args().case_file)