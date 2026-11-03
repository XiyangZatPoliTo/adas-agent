import pytest
from langchain_core.messages import AIMessage

from BFF_Bot.eval.golden import evaluate_golden
from BFF_Bot.eval.retrieval import evaluate_retrieval
from BFF_Bot.rag import qa

HIT = {"source": "a.md", "distance": 0.7, "text": "t"}


class FakeLLM:
    def __init__(self):
        self.seen = []

    def invoke(self, messages):
        self.seen.append(messages)
        return AIMessage(content="ANS")


def test_retrieval_metrics_and_threshold():
    table = {
        "q1": [{"source": "a.md", "distance": 0.7}],
        "q2": [{"source": "a.md", "distance": 0.9}, {"source": "b.md", "distance": 1.0}],
        "q3": [{"source": "a.md", "distance": 1.3}],
    }
    cases = [{"q": "q1", "expect": "a.md"}, {"q": "q2", "expect": "b.md"}, {"q": "q3", "expect": None}]
    r = evaluate_retrieval(cases, lambda q, k: table[q][:k])
    assert r["hit@1"] == 0.5 and r["hit@3"] == 1.0 and r["mrr"] == pytest.approx(0.75)
    assert r["suggested_threshold"] == pytest.approx(1.1)  # 介于最大相关距离 0.9 和最小无关距离 1.3 之间
    assert r["misses"][0]["q"] == "q2"


def test_golden_eval_counts_failures():
    rows = [
        {"log_file": "a", "note_time": "t", "expected_verdict": "fault_chain",
         "expected_dtc": "C1A01", "expected_funcs": "ACC;AEB"},
        {"log_file": "b", "note_time": "t", "expected_verdict": "driver_action",
         "expected_dtc": "", "expected_funcs": ""},
    ]
    fake = {"a": {"verdict": "fault_chain", "findings": [{"dtc": "C1A01", "degraded_functions": ["ACC", "AEB"]}]},
            "b": {"verdict": "inconclusive", "findings": []}}
    r = evaluate_golden(rows, lambda f, t: fake[f])
    assert r["verdict_acc"] == 0.5 and r["dtc_acc"] == 1.0 and r["funcs_acc"] == 1.0
    assert r["failures"][0]["row"] == "b"


def test_distance_threshold_refuses_without_calling_llm(monkeypatch):
    monkeypatch.setattr(qa, "kb_search", lambda q, k=3: [HIT])
    fake = FakeLLM()
    r = qa.answer_question("x", llm=fake, max_distance=0.5)
    assert "暂无相关内容" in r["answer"] and fake.seen == []


def test_threshold_read_from_env(monkeypatch):
    monkeypatch.setattr(qa, "kb_search", lambda q, k=3: [HIT])
    monkeypatch.setenv("KB_MAX_DISTANCE", "0.5")
    fake = FakeLLM()
    assert "暂无相关内容" in qa.answer_question("x", llm=fake)["answer"] and fake.seen == []