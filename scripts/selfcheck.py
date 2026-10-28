"""一键自检:每个场景输出一行摘要,方便只贴几行进行核对。"""
from pathlib import Path

import pandas as pd

from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.loaders.dlt_csv import load_dlt_csv

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
ROLE_ABBR = {"sensor_abnormal": "sen", "dtc_set": "dtc", "function_degrade": "fun"}


def main() -> None:
    logbook = pd.read_csv(LOG_DIR / "logbook.csv", dtype=str)
    for _, e in logbook.iterrows():
        r = analyze_window(load_dlt_csv(LOG_DIR / e["log_file"]), e["note_time"])
        f = r["findings"][0] if r["findings"] else None
        chain = ">".join(ROLE_ABBR[x["role"]] for x in f["evidence"]) if f else "-"
        print(f"{e['log_file'][:7]} | {r['verdict']} | {r['confidence']} | "
              f"dtc={f['dtc'] if f else '-'} | funcs={','.join(f['degraded_functions']) if f else '-'} | "
              f"chain={chain} | unclassified={len(r['unclassified_novel'])} | notes={len(r['notes'])}")


if __name__ == "__main__":
    main()