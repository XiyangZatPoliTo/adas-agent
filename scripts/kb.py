import argparse

from BFF_Bot.rag.store import build_index, search

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd", required=True)
sub.add_parser("build")
s = sub.add_parser("search")
s.add_argument("query")
args = parser.parse_args()

if args.cmd == "build":
    store = build_index()
    print("已入库的块数:", store._collection.count())
else:
    for r in search(args.query):
        print(f"{r['distance']:.3f} | {r['source']} | {r['text'][:60]}")