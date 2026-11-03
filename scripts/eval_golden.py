from pathlib import Path

import pandas as pd

from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.eval.golden import evaluate_golden
from BFF_Bot.loaders.dlt_csv import load_dlt_csv

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "logs"  # 试点时改成真实日志所在的(内网)目录
rows = pd.read_csv(ROOT / "data" / "eval" / "golden.csv", dtype=str, keep_default_na=False).to_dict("records")
r = evaluate_golden(rows, lambda f, t: analyze_window(load_dlt_csv(LOG_DIR / f), t))
print(f"n={r['n']} verdict={r['verdict_acc']:.2f} dtc={r['dtc_acc']:.2f} funcs={r['funcs_acc']:.2f}")
for x in r["failures"]:
    print("FAIL", x)