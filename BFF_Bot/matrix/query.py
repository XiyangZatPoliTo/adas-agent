"""版本化查询与版本差异对比。
Versioned lookup and version diff.
"""


def lookup(matrix: dict, code: str, version: str = None) -> dict:
    version = version or list(matrix)[-1]  # 默认最新版本(字典保持 sheet 顺序)
    if version not in matrix:
        return {"found": False, "error": f"未知版本 {version}", "versions": list(matrix)}
    rec = matrix[version].get(code.strip().upper())
    if rec is None:
        return {"found": False, "code": code.strip().upper(), "version": version}
    return {"found": True, "code": code.strip().upper(), "version": version, **rec}


def _delta(x: dict, y: dict) -> dict:
    d = {}
    for k in x:
        if k == "effects":
            for f in x[k]:  # 功能影响逐个功能比较,输出更直观
                if x[k][f] != y[k].get(f):
                    d[f"effect:{f}"] = (x[k][f], y[k].get(f))
        elif x[k] != y[k]:
            d[k] = (x[k], y[k])
    return d


def diff_versions(matrix: dict, old: str, new: str) -> dict:
    """对比两个版本:新增、删除、哪些故障码的内容变了。这正是"错误码含义随版本变化"的痛点。"""
    a, b = matrix[old], matrix[new]
    changed = {}
    for c in sorted(set(a) & set(b)):
        delta = _delta(a[c], b[c])
        if delta:
            changed[c] = delta
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)), "changed": changed}