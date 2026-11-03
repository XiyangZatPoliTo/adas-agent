from pathlib import Path

import yaml

from BFF_Bot.eval.retrieval import evaluate_retrieval
from BFF_Bot.rag.store import search

cases = yaml.safe_load((Path(__file__).resolve().parents[1] / "data" / "eval" / "retrieval.yaml").read_text(encoding="utf-8"))
r = evaluate_retrieval(cases, lambda q, k: search(q, k=k))
# 只输出一行摘要;有失败再逐条列出,方便只把关键信息贴出来
print(" ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in r.items() if k != "misses"))
for m in r["misses"]:
    print("MISS", m)