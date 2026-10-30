import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from BFF_Bot.api.app import app, get_qa_llm
from BFF_Bot.rag import qa

HIT = {"source": "radar_comm_loss.md", "distance": 0.7, "text": "雷达排查步骤"}


class FakeLLM:
    def __init__(self):
        self.seen = []

    def invoke(self, messages):
        self.seen.append(messages)
        return AIMessage(content="ANS")


def test_answer_puts_question_and_snippets_into_prompt(monkeypatch):
    monkeypatch.setattr(qa, "kb_search", lambda q, k=3: [HIT])
    fake = FakeLLM()
    r = qa.answer_question("雷达掉线怎么办", llm=fake)
    sent = fake.seen[0][-1].content
    assert "雷达掉线怎么办" in sent and "radar_comm_loss.md" in sent
    assert r["answer"] == "ANS" and r["retrieved"] == [{"source": "radar_comm_loss.md", "distance": 0.7}]


def test_empty_index_does_not_call_llm(monkeypatch):
    monkeypatch.setattr(qa, "kb_search", lambda q, k=3: [])
    fake = FakeLLM()
    assert "无法回答" in qa.answer_question("任意问题", llm=fake)["answer"]
    assert fake.seen == []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(qa, "kb_search", lambda q, k=3: [HIT])
    app.dependency_overrides[get_qa_llm] = lambda: FakeLLM()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ask_endpoint(client):
    r = client.post("/ask", json={"question": "雷达掉线怎么排查"})
    assert r.status_code == 200 and r.json()["answer"] == "ANS"


def test_ask_validates_length(client):
    assert client.post("/ask", json={"question": "a"}).status_code == 422
    assert client.post("/ask", json={"question": "问" * 501}).status_code == 422