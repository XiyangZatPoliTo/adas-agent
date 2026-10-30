"""知识库问答:检索 -> 基于片段回答 -> 标注来源。
Knowledge Q&A: retrieve -> answer from snippets only -> cite sources.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from BFF_Bot.llm import get_llm
from BFF_Bot.prompts import QA_SYSTEM_PROMPT
from BFF_Bot.rag.store import search as kb_search


def answer_question(question: str, llm=None, k: int = 3) -> dict:
    hits = kb_search(question, k=k)
    if not hits:
        # 索引为空时不必调用 LLM:省钱,也避免模型在没有材料时"自由发挥"
        return {"answer": "知识库为空或尚未建立索引,无法回答。", "retrieved": []}
    model = llm or get_llm()  # 可注入,测试用假模型
    msg = model.invoke([SystemMessage(content=QA_SYSTEM_PROMPT),
                        HumanMessage(content=json.dumps({"问题": question, "知识库片段": hits},
                                                        ensure_ascii=False))])
    # retrieved 是"检索到了什么",不等于"回答用了什么";实际引用以回答里的来源标注为准
    return {"answer": msg.content,
            "retrieved": [{"source": h["source"], "distance": h["distance"]} for h in hits]}