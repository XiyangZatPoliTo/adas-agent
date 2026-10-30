import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from BFF_Bot.api.app import app, get_graph
from BFF_Bot.graph import workflow
from BFF_Bot.tools import registry
from scripts.generate_sample_log import CASES, build_case, fmt


class FakeLLM:
    def invoke(self, messages):
        return AIMessage(content="REPORT")


def body(file, case):
    return {"log_file": file, "note_time": fmt(CASES[case]["note_ms"])}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "LOG_DIR", tmp_path)
    build_case(CASES["case_01_radar_comm_loss"]).to_csv(tmp_path / "c1.csv", index=False, encoding="utf-8")
    build_case(CASES["case_04_driver_cancel_acc"]).to_csv(tmp_path / "c4.csv", index=False, encoding="utf-8")
    monkeypatch.setattr(workflow, "kb_search", lambda q, k=3: [
        {"source": "radar_comm_loss.md", "distance": 0.7, "text": "雷达排查"}])
    graph = workflow.build_graph(llm=FakeLLM())
    app.dependency_overrides[get_graph] = lambda: graph  # 用假模型的图替换真实的图
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_fault_analysis_completes(client):
    r = client.post("/analyze", json=body("c1.csv", "case_01_radar_comm_loss"))
    j = r.json()
    assert r.status_code == 200 and j["status"] == "completed"
    assert j["verdict"] == "fault_chain" and j["report"] == "REPORT"


def test_driver_action_requires_confirmation_then_completes(client):
    j = client.post("/analyze", json=body("c4.csv", "case_04_driver_cancel_acc")).json()
    assert j["status"] == "awaiting_confirmation" and j["report"] is None
    assert "视频" in j["confirmation"]["question"]
    r2 = client.post(f"/analyze/{j['thread_id']}/confirm", json={"confirmed": True})
    assert r2.status_code == 200 and r2.json()["status"] == "completed" and r2.json()["report"] == "REPORT"
    # 已完成的任务不能重复确认
    assert client.post(f"/analyze/{j['thread_id']}/confirm", json={"confirmed": True}).status_code == 409


def test_confirm_unknown_thread_is_404(client):
    assert client.post("/analyze/no-such-id/confirm", json={"confirmed": True}).status_code == 404


def test_missing_file_is_404(client):
    r = client.post("/analyze", json=body("nope.csv", "case_01_radar_comm_loss"))
    assert r.status_code == 404


def test_bad_time_is_422(client):
    r = client.post("/analyze", json={"log_file": "c1.csv", "note_time": "not-a-time"})
    assert r.status_code == 422


def test_missing_field_is_422(client):
    assert client.post("/analyze", json={}).status_code == 422  # 由 Pydantic 自动校验


def test_response_includes_evidence(client):
    j = client.post("/analyze", json=body("c1.csv", "case_01_radar_comm_loss")).json()
    assert j["evidence"]["findings"][0]["dtc"] == "C1A01"