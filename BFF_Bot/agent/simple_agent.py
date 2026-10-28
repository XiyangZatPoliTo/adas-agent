"""手写的最小 Agent 循环:模型 -> 工具 -> 模型 ... 直到不再调用工具。
后面会用 LangGraph 把它变成可观测、可控的状态流。
Minimal handwritten agent loop; LangGraph will replace it later.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from BFF_Bot.llm import get_llm
from BFF_Bot.tools.registry import ALL_TOOLS, TOOLS_BY_NAME

MAX_STEPS = 5  # 步数上限:防止模型反复调用工具造成死循环和费用失控


def _execute(call: dict):
    tool = TOOLS_BY_NAME.get(call["name"])
    if tool is None:
        return {"error": f"未知工具: {call['name']}"}
    try:
        return tool.invoke(call["args"])
    except Exception as e:  # 工具出错不应让整个 Agent 崩溃:把错误回传给模型,让它自己调整
        return {"error": f"{type(e).__name__}: {e}"}


def run_agent(question: str, system_prompt: str, llm=None, verbose: bool = True) -> str:
    # llm 可注入:测试时传入假模型,不产生 API 调用和费用
    llm = (llm or get_llm()).bind_tools(ALL_TOOLS)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=question)]
    for _ in range(MAX_STEPS):
        ai = llm.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:  # 模型不再请求工具 = 最终回答
            return ai.content
        for call in ai.tool_calls:
            content = json.dumps(_execute(call), ensure_ascii=False, default=str)
            if verbose:
                print(f"[工具] {call['name']}({call['args']}) -> {len(content)} 字符")
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
    return "(已达到最大步数,未得出最终回答)"