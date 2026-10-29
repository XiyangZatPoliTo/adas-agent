"""LangGraph 工作流:分析 -> (检索 | 人工确认) -> 报告。
流程结构是确定的;LLM 只用在需要语言表达的"报告"节点。
Workflow structure is deterministic; the LLM is used only where language is needed.
"""
import json
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from BFF_Bot.llm import get_llm
from BFF_Bot.prompts import WORKFLOW_REPORT_PROMPT
from BFF_Bot.rag.store import search as kb_search
from BFF_Bot.tools.registry import analyze_log_window


class State(TypedDict, total=False):
    """图的共享状态:节点之间只通过它传数据。每个节点只返回自己更新的那几个键。"""
    log_file: str
    note_time: str
    evidence: dict          # 分析流水线的证据包
    knowledge: list         # 知识库检索结果
    knowledge_error: str
    human_decision: str     # confirmed / rejected
    report: str


def analyze_node(state: State) -> dict:
    # 确定性节点:直接调用分析工具(其中已含路径穿越防护),不经过 LLM
    return {"evidence": analyze_log_window.invoke(
        {"log_file": state["log_file"], "note_time": state["note_time"]})}


def route_after_analyze(state: State) -> str:
    """条件边:按分析结论决定下一个节点。这就是"流程由代码掌控"的体现。"""
    ev = state["evidence"]
    if "error" in ev:
        return "fail"
    verdict = ev.get("verdict")
    if verdict == "driver_action":
        return "human_confirm"  # 疑似人为操作:必须先让人看视频
    if verdict in ("fault_chain", "unexplained_degrade"):
        return "retrieve"
    return "report"             # inconclusive:直接出报告,报告里如实说明证据不足


def retrieve_node(state: State) -> dict:
    ev = state["evidence"]
    f = next((x for x in ev["findings"] if x.get("dtc")), None)
    if f:
        desc = (f.get("dtc_info") or {}).get("description", "")
        query = f"{f['dtc']} {desc} 排查".strip()  # 用"故障码 + 含义"做查询,命中更准
    else:
        query = "功能降级 排查步骤"
    try:
        return {"knowledge": kb_search(query, k=3)}
    except Exception as e:  # 检索失败不应让整个流程崩溃;记录原因,报告里如实说明
        return {"knowledge": [], "knowledge_error": f"{type(e).__name__}: {e}"}


def human_confirm_node(state: State) -> dict:
    # 注意:恢复执行时本节点会从头重新运行,所以 interrupt() 之前不能放有副作用的代码。
    answer = interrupt({
        "question": "日志显示功能由驾驶员操作退出。请对照视频确认是否为人为操作 (yes/no)",
        "summary": state["evidence"]["summary"],
    })
    ok = str(answer).strip().lower() in ("yes", "y", "是", "确认")
    return {"human_decision": "confirmed" if ok else "rejected"}


def fail_node(state: State) -> dict:
    ev = state["evidence"]
    return {"report": f"分析失败: {ev['error']}。可用日志文件: {ev.get('available_files', '无')}"}


def make_report_node(llm=None):
    def report_node(state: State) -> dict:
        model = llm or get_llm()  # llm 可注入:测试用假模型,零费用
        materials = {
            "证据包": state["evidence"],
            "知识库片段": state.get("knowledge", []),
            "知识库检索错误": state.get("knowledge_error"),
            "人工确认结果": state.get("human_decision", "未触发"),
        }
        msg = model.invoke([SystemMessage(content=WORKFLOW_REPORT_PROMPT),
                            HumanMessage(content=json.dumps(materials, ensure_ascii=False, default=str))])
        return {"report": msg.content}
    return report_node


def build_graph(llm=None, checkpointer=None):
    g = StateGraph(State)
    g.add_node("analyze", analyze_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("human_confirm", human_confirm_node)
    g.add_node("report", make_report_node(llm))
    g.add_node("fail", fail_node)

    g.add_edge(START, "analyze")
    g.add_conditional_edges("analyze", route_after_analyze,
                            {k: k for k in ("fail", "human_confirm", "retrieve", "report")})
    g.add_edge("retrieve", "report")
    g.add_edge("human_confirm", "report")
    g.add_edge("report", END)
    g.add_edge("fail", END)
    # interrupt 需要检查点保存暂停时的状态;生产环境应换成 sqlite/postgres 持久化
    return g.compile(checkpointer=checkpointer or InMemorySaver())