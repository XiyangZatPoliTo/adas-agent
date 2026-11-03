import argparse
import json
from pathlib import Path

from BFF_Bot.matrix.importer import MATRIX_JSON, import_matrix, load_matrix, save_matrix
from BFF_Bot.matrix.query import diff_versions, lookup
from scripts.make_sample_matrix import write_sample

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "matrix" / "sample_matrix.xlsx"

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("make-sample")
i = sub.add_parser("import")
i.add_argument("xlsx", nargs="?", default=str(SAMPLE))
lk = sub.add_parser("lookup")
lk.add_argument("code")
lk.add_argument("--version")
d = sub.add_parser("diff")
d.add_argument("old")
d.add_argument("new")
a = p.parse_args()

if a.cmd == "make-sample":
    write_sample(SAMPLE)
    print("已生成", SAMPLE)
elif a.cmd == "import":
    m = import_matrix(a.xlsx)
    save_matrix(m)
    print({v: len(t) for v, t in m.items()}, "->", MATRIX_JSON)
elif a.cmd == "lookup":
    print(json.dumps(lookup(load_matrix(), a.code, a.version), ensure_ascii=False))
else:
    print(json.dumps(diff_versions(load_matrix(), a.old, a.new), ensure_ascii=False, indent=2))