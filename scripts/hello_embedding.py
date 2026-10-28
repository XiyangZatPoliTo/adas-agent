"""验证 Embedding 能用,并直观看到"语义相近 = 向量相近"。"""
import numpy as np

from BFF_Bot.llm import get_embeddings


def cos(a, b) -> float:
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


emb = get_embeddings()
docs = ["前向雷达通信丢失会导致 ACC 降级", "摄像头被遮挡会影响车道保持"]
vecs = emb.embed_documents(docs)  # 文档向量
q = emb.embed_query("雷达掉线")      # 查询向量(与文档用不同入口,有的模型会区别对待)

print("向量条数/维度:", len(vecs), len(vecs[0]))
print("查询与文档0(雷达)相似度:", round(cos(q, vecs[0]), 3))
print("查询与文档1(摄像头)相似度:", round(cos(q, vecs[1]), 3))