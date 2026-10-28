"""运行完整分析流水线,输出结构化 JSON(这就是后面交给 LLM 的"证据包")。"""
import argparse
import json
from pathlib import Path

import pandas as pd

from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.loaders.dlt_csv import load_dlt_csv

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"


def main(case_file: str) -> None:
    logbook = pd.read_csv(LOG_DIR / "logbook.csv", dtype=str)
    entry = logbook[logbook["log_file"] == case_file].iloc[0]
    result = analyze_window(load_dlt_csv(LOG_DIR / case_file), entry["note_time"])
    result["logbook"] = {"time": entry["note_time"], "note": entry["note"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_file", help="例如 case_01_radar_comm_loss.csv")
    main(parser.parse_args().case_file)