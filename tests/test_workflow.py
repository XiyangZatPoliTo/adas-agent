from langchain_core.messages import AIMessage
from langgraph.types import Command

from BFF_Bot.graph import workflow
from BFF_Bot.tools import registry
from scripts.generate_sample_log import CASES, build_case, fmt


class FakeLLM:
    def __init__(self, reply="REPORT"):
        self.reply, self.seen = reply, []

    def invoke(self, messages):
        self.seen.append(messages)
        return AIMessage(content=self.reply)


def run_graph(tmp_path, monkeypatch, case, llm, log_file="c.csv", thread="t"):
    monkeypatch.setattr(registry, "LOG_DIR", tmp_path)  # 工具只读临时目录
    build_case(CASES[case]).to_csv(tmp_path / "c.csv", index=False, encoding="utf-8")
    monkeypatch.setattr(workflow, "kb_search", lambda q, k=3: [
        {"source": "radar_comm_loss.md", "distance": 0.7, "text": "雷达排查"}])
    graph = workflow.build_graph(llm=llm)
    cfg = {"configurable": {"thread_id": thread}}
    out = graph.invoke({"log_file": log_file, "note_time": fmt(CASES[case]["note_ms"])}, cfg)
    return graph, cfg, out


def test_fault_path_retrieves_and_reports(tmp_path, monkeypatch):
    fake = FakeLLM()
    graph, cfg, out = run_graph(tmp_path, monkeypatch, "case_01_radar_comm_loss", fake)
    assert out["report"] == "REPORT" and graph.get_state(cfg).next == ()
    sent = fake.seen[0][-1].content  # 报告节点收到的材料
    assert "C1A01" in sent and "radar_comm_loss.md" in sent


def test_driver_path_pauses_for_human_then_resumes(tmp_path, monkeypatch):
    fake = FakeLLM()
    graph, cfg, _ = run_graph(tmp_path, monkeypatch, "case_04_driver_cancel_acc", fake)
    assert graph.get_state(cfg).next == ("human_confirm",)  # 停在人工确认
    assert fake.seen == []                                   # 此时还没调用 LLM
    out = graph.invoke(Command(resume="yes"), cfg)
    assert out["human_decision"] == "confirmed" and "confirmed" in fake.seen[0][-1].content


def test_human_rejection_is_passed_to_report(tmp_path, monkeypatch):
    fake = FakeLLM()
    graph, cfg, _ = run_graph(tmp_path, monkeypatch, "case_04_driver_cancel_acc", fake, thread="t2")
    out = graph.invoke(Command(resume="no"), cfg)
    assert out["human_decision"] == "rejected" and "rejected" in fake.seen[0][-1].content


def test_missing_file_fails_without_calling_llm(tmp_path, monkeypatch):
    fake = FakeLLM()
    _, _, out = run_graph(tmp_path, monkeypatch, "case_01_radar_comm_loss", fake, log_file="nope.csv")
    assert out["report"].startswith("分析失败") and fake.seen == []


def test_routing():
    r = workflow.route_after_analyze
    assert r({"evidence": {"error": "x"}}) == "fail"
    assert r({"evidence": {"verdict": "driver_action"}}) == "human_confirm"
    assert r({"evidence": {"verdict": "fault_chain"}}) == "retrieve"
    assert r({"evidence": {"verdict": "inconclusive"}}) == "report"