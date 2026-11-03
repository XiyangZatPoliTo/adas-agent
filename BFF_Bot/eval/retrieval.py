"""检索评估:用"问题 -> 期望命中文档"的评估集量化检索质量,并给出拒答距离阈值的建议。
Retrieval evaluation: quantify retrieval quality and suggest a refusal distance threshold.
"""


def evaluate_retrieval(cases: list[dict], search_fn, k: int = 3) -> dict:
    """cases: [{"q": 问题, "expect": 应命中的文档名或 None}]。search_fn(q, k) 返回带 source/distance 的列表。
    expect 为 None 表示"知识库里本来就没有答案",用来校准阈值。search_fn 可注入,所以能用假检索做单元测试。"""
    in_scope = [c for c in cases if c["expect"]]
    out_scope = [c for c in cases if not c["expect"]]
    ranks, misses, in_d, out_d = [], [], [], []
    for c in in_scope:
        hits = search_fn(c["q"], k)
        srcs = [h["source"] for h in hits]
        rank = srcs.index(c["expect"]) + 1 if c["expect"] in srcs else None  # 期望文档排第几
        ranks.append(rank)
        if rank != 1:
            misses.append({"q": c["q"], "expect": c["expect"], "got": srcs})
        if hits:
            in_d.append(hits[0]["distance"])
    for c in out_scope:
        hits = search_fn(c["q"], k)
        if hits:
            out_d.append(hits[0]["distance"])

    n = len(in_scope) or 1
    # 阈值只有在"相关问题的最大距离 < 无关问题的最小距离"时才能给出;
    # 两类距离重叠就说明阈值分不开它们,硬给一个数反而有害,此时返回 None。
    threshold = round((max(in_d) + min(out_d)) / 2, 3) if in_d and out_d and max(in_d) < min(out_d) else None
    return {"n_in": len(in_scope), "n_out": len(out_scope),
            "hit@1": sum(r == 1 for r in ranks) / n,
            f"hit@{k}": sum(r is not None for r in ranks) / n,
            "mrr": sum(1 / r for r in ranks if r) / n,  # 平均倒数排名:越接近 1,正确文档越靠前
            "in_top1_max": max(in_d, default=None), "out_top1_min": min(out_d, default=None),
            "suggested_threshold": threshold, "misses": misses}