from langchain_core.messages import AIMessage

from BFF_Bot.agent.simple_agent import MAX_STEPS, run_agent
from BFF_Bot.tools import registry
from scripts.generate_sample_log import CASES, build_case, fmt


class FakeLLM:
    """假模型:按剧本依次返回预设回复,并记录每次收到的消息。"""
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def call_msg(name, args, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid, "type": "tool_call"}])


def test_agent_runs_tool_then_answers():
    fake = FakeLLM([call_msg("lookup_dtc_tool", {"code": "C1A01"}), AIMessage(content="最终报告")])
    assert run_agent("q", "sys", llm=fake, verbose=False) == "最终报告"
    assert "前向毫米波雷达" in fake.seen[1][-1].content  # 工具结果确实回传给了模型


def test_unknown_tool_is_reported_back_to_model():
    fake = FakeLLM([call_msg("nope", {}), AIMessage(content="ok")])
    run_agent("q", "sys", llm=fake, verbose=False)
    assert "未知工具" in fake.seen[1][-1].content


def test_max_steps_guard():
    fake = FakeLLM([call_msg("lookup_dtc_tool", {"code": "C1A01"}, f"c{i}") for i in range(MAX_STEPS)])
    assert "最大步数" in run_agent("q", "sys", llm=fake, verbose=False)


def test_analysis_tool_blocks_path_traversal_and_missing_file():
    r = registry.analyze_log_window.invoke({"log_file": "../../.env", "note_time": "2026-01-15 14:01:14"})
    assert "error" in r and "available_files" in r


def test_analysis_tool_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "LOG_DIR", tmp_path)  # 工具只读 tmp 目录,不依赖磁盘上的 data/logs
    build_case(CASES["case_01_radar_comm_loss"]).to_csv(tmp_path / "x.csv", index=False, encoding="utf-8")
    r = registry.analyze_log_window.invoke(
        {"log_file": "x.csv", "note_time": fmt(CASES["case_01_radar_comm_loss"]["note_ms"])})
    assert r["verdict"] == "fault_chain" and r["findings"][0]["dtc"] == "C1A01"