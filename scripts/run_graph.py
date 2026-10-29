"""运行工作流:打印经过的节点;遇到人工确认就暂停并等待输入。"""
import argparse
import uuid

from langgraph.types import Command

from BFF_Bot.graph.workflow import build_graph


def main(log_file: str, note_time: str) -> None:
    graph = build_graph()
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}  # 暂停/恢复必须用同一个 thread_id

    def run(inp):
        for chunk in graph.stream(inp, cfg, stream_mode="updates"):
            for node in chunk:
                if node != "__interrupt__":
                    print(f"→ {node}")

    run({"log_file": log_file, "note_time": note_time})
    while graph.get_state(cfg).next:  # next 非空 = 图停在某个节点,等待人工输入
        payload = graph.get_state(cfg).tasks[0].interrupts[0].value
        print(f"\n[需要人工确认] {payload['question']}\n系统判断: {payload['summary']}")
        run(Command(resume=input("请输入 yes/no: ")))
    print("\n" + graph.get_state(cfg).values["report"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file")
    parser.add_argument("note_time", help='例如 "2026-01-15 14:01:14.000"')
    args = parser.parse_args()
    main(args.log_file, args.note_time)