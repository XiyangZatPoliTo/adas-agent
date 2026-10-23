import json
from pathlib import Path

_DTC_PATH = Path(__file__).resolve().parents[2] / "data" / "dtc_table.json"


def _load_table() -> dict:
    with open(_DTC_PATH, encoding="utf-8") as f:
        return json.load(f)


def lookup_dtc(code: str) -> dict:
    """根据故障码查询其含义、影响功能、严重程度和常见原因。"""
    normalized = code.strip().upper()
    table = _load_table()
    if normalized not in table:
        return {"found": False, "code": normalized, "message": f"故障码 {normalized} 不在知识表中"}
    return {"found": True, "code": normalized, **table[normalized]}