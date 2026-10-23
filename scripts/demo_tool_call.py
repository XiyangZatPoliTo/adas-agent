import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from BFF_Bot.llm import get_llm
from BFF_Bot.prompts import SYSTEM_PROMPT
from BFF_Bot.tools.registry import ALL_TOOLS, TOOLS_BY_NAME

QUESTION = "车辆报了故障码 C1A03,这是什么意思?会影响哪些功能?"

llm = get_llm().bind_tools(ALL_TOOLS)

messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=QUESTION),
]

# 第 1 轮:模型决定是否调用工具
ai_msg = llm.invoke(messages)
messages.append(ai_msg)
print("模型请求的工具调用:", ai_msg.tool_calls)

if ai_msg.tool_calls:
    # 由我们的代码执行工具,并把结果回传
    for call in ai_msg.tool_calls:
        result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
        print("工具返回:", result)
        messages.append(
            ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=call["id"],
            )
        )
    # 第 2 轮:模型基于工具结果给出最终回答
    final = llm.invoke(messages)
else:
    # 没有工具调用,第一轮的回答就是最终回答
    final = ai_msg

print("最终回答:", final.content)