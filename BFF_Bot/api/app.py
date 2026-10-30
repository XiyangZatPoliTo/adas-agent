"""FastAPI 服务:把工作流暴露成 HTTP 接口。
人工确认通过"两步调用"实现:第一次返回 awaiting_confirmation,第二次提交确认结果。
Two-step call for human confirmation: first call returns awaiting_confirmation, second submits the decision.
"""
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from BFF_Bot.graph.workflow import build_graph

app = FastAPI(title="BFF Bot - ADAS 降级根因分析", version="0.1.0")

from BFF_Bot.rag.qa import answer_question


_graph = None


def get_graph():
    """图只构建一次并复用。检查点存在内存里,服务重启后进行中的任务会丢失(生产应换持久化)。
    同时它是"依赖注入点":测试时可以替换成带假模型的图,不产生任何 API 费用。"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class AnalyzeRequest(BaseModel):
    log_file: str = Field(..., examples=["case_01_radar_comm_loss.csv"])
    note_time: str = Field(..., examples=["2026-01-15 14:01:14.000"])


class ConfirmRequest(BaseModel):
    confirmed: bool  # 人工看完视频后的结论:是否确认为人为操作


class AnalyzeResponse(BaseModel):
    thread_id: str
    status: Literal["completed", "awaiting_confirmation"]
    verdict: str | None = None
    confidence: str | None = None
    report: str | None = None
    confirmation: dict | None = None  # 等待人工确认时,给人看的问题和系统判断
    evidence: dict | None = None # 完整证据包：界面用它展示证据链（等待确认时也能看到）


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}  # 暂停/恢复必须用同一个 thread_id


def _to_response(graph, cfg, thread_id: str) -> AnalyzeResponse:
    st = graph.get_state(cfg)
    ev = st.values.get("evidence") or {}
    if st.next:  # next 非空 = 图停在人工确认节点
        return AnalyzeResponse(thread_id=thread_id, status="awaiting_confirmation",
                               verdict=ev.get("verdict"), confirmation=st.tasks[0].interrupts[0].value, evidence=ev or None)
    return AnalyzeResponse(thread_id=thread_id, status="completed", verdict=ev.get("verdict"),
                           confidence=ev.get("confidence"), report=st.values.get("report"), evidence=ev or None)


@app.get("/health")
def health():
    return {"status": "ok"}


# 用普通 def 而不是 async def:内部是阻塞的 LLM 调用,FastAPI 会把它放进线程池执行,不会卡住事件循环。
@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, graph=Depends(get_graph)):
    thread_id = str(uuid.uuid4())
    cfg = _cfg(thread_id)
    graph.invoke({"log_file": req.log_file, "note_time": req.note_time}, cfg)
    ev = graph.get_state(cfg).values.get("evidence", {})
    if "error" in ev:
        # 客户端错误用 4xx 明确告知;文件不存在带 available_files,其余(如时间格式)视为参数错误
        raise HTTPException(status_code=404 if "available_files" in ev else 422, detail=ev["error"])
    return _to_response(graph, cfg, thread_id)


@app.post("/analyze/{thread_id}/confirm", response_model=AnalyzeResponse)
def confirm(thread_id: str, req: ConfirmRequest, graph=Depends(get_graph)):
    cfg = _cfg(thread_id)
    st = graph.get_state(cfg)
    if not st.values:
        raise HTTPException(status_code=404, detail="thread_id 不存在")
    if not st.next:  # 防止重复确认:已完成的任务不能再次恢复
        raise HTTPException(status_code=409, detail="该任务不在等待确认状态(可能已完成)")
    graph.invoke(Command(resume="yes" if req.confirmed else "no"), cfg)
    return _to_response(graph, cfg, thread_id)


class AskRequest(BaseModel):
    # 长度限制:拦截空问题和超长输入(超长输入既浪费费用,也是提示词注入的常见入口)
    question: str = Field(..., min_length=2, max_length=500, examples=["摄像头被冰遮住了,怎么排查?"])


class AskResponse(BaseModel):
    answer: str
    retrieved: list[dict]


def get_qa_llm():
    """依赖注入点:生产环境返回 None(使用默认模型),测试替换为假模型。"""
    return None


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, llm=Depends(get_qa_llm)):
    return answer_question(req.question, llm=llm)