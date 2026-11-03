"""知识库问答:检索 -> (距离过滤) -> 基于片段回答 -> 标注来源。
Knowledge Q&A: retrieve -> distance guard -> answer from snippets only -> cite sources.
"""
import json
import os

from langchain_core.messages import HumanMessage, SystemMessage

from BFF_Bot.llm import get_llm
from BFF_Bot.prompts import QA_SYSTEM_PROMPT
from BFF_Bot.rag.store import search as kb_search


def _default_max_distance():
    v = os.getenv("KB_MAX_DISTANCE")  # 由评估脚本给出建议值;为空表示不启用距离拒答
    return float(v) if v else None


def answer_question(question: str, llm=None, k: int = 3, max_distance=None) -> dict:
    hits = kb_search(question, k=k)
    if not hits:
        return {"answer": "知识库为空或尚未建立索引,无法回答。", "retrieved": []}
    retrieved = [{"source": h["source"], "distance": h["distance"]} for h in hits]
    limit = max_distance if max_distance is not None else _default_max_distance()
    # 距离越小越相关。超过阈值的片段视为无关:代码层面的硬拒答,不依赖模型是否"听话"
    relevant = [h for h in hits if limit is None or h["distance"] <= limit]
    if not relevant:
        return {"answer": "知识库中暂无相关内容。", "retrieved": retrieved}
    model = llm or get_llm()  # 可注入,测试用假模型
    msg = model.invoke([SystemMessage(content=QA_SYSTEM_PROMPT),
                        HumanMessage(content=json.dumps({"问题": question, "知识库片段": relevant},
                                                        ensure_ascii=False))])
    return {"answer": msg.content, "retrieved": retrieved}