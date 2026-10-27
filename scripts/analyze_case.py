"""端到端演示:logbook 时间 -> 窗口 -> 窗口内"新出现"的消息模板。"""
import argparse
from pathlib import Path

import pandas as pd

from BFF_Bot.analysis.window import find_novel_templates
from BFF_Bot.loaders.dlt_csv import load_dlt_csv

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"


def main(case_file: str) -> None:
    logbook = pd.read_csv(LOG_DIR / "logbook.csv", dtype=str)
    entry = logbook[logbook["log_file"] == case_file].iloc[0]
    df = load_dlt_csv(LOG_DIR / case_file)
    novel, meta = find_novel_templates(df, entry["note_time"])

    print(f"测试员记录: {entry['note']}  (时间 {entry['note_time']})")
    print(f"窗口: {meta['window_start']} ~ {meta['window_end']},窗口内 {meta['rows_in_window']} 行,"
          f"基线 {meta['baseline_seconds']:.1f} 秒")
    if not meta["baseline_ok"]:
        print("提示: 基线过短,新颖性结论可信度较低")
    if novel.empty:
        print("窗口内没有新出现的文本消息模板")
        return
    view = novel.assign(first_time=novel["first_time"].dt.strftime("%H:%M:%S.%f").str[:-3],
                        example=novel["example"].str.slice(0, 70))
    print(view[["first_time", "ecu", "level", "count", "example"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_file", help="例如 case_01_radar_comm_loss.csv")
    main(parser.parse_args().case_file)