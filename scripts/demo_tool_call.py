import json

from langchain_core.messages import HumanMessage, ToolMessage

from BFF_Bot.llm import get_llm
from BFF_Bot.tools.registry import ALL_TOOLS, TOOLS_BY_NAME

llm = get_llm().bind_tools(ALL_TOOLS)

messages = [HumanMessage(content="X9999是什么故障码？")]

# 第 1 轮:模型决定是否调用工具
ai_msg = llm.invoke(messages)
messages.append(ai_msg)
print("模型请求的工具调用:", ai_msg.tool_calls)

# 由我们的代码真正执行工具,并把结果回传
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
print("最终回答:", final.content)

