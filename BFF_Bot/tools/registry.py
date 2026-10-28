from pathlib import Path

import pandas as pd
from langchain_core.tools import tool

from BFF_Bot.analysis.pipeline import analyze_window
from BFF_Bot.loaders.dlt_csv import load_dlt_csv
from BFF_Bot.tools.dtc import lookup_dtc

from BFF_Bot.rag.store import search as kb_search

LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"


@tool
def lookup_dtc_tool(code: str) -> dict:
    """查询 ADAS 故障码(DTC)的含义、受影响的功能、严重程度和常见原因。
    当用户提到类似 C1A01、U0100 这样的故障码时使用。

    Args:
        code: 故障码,例如 C1A01
    """
    return lookup_dtc(code)


@tool
def analyze_log_window(log_file: str, note_time: str) -> dict:
    """分析某个日志文件在指定时间点附近的功能降级/故障事件,返回结构化证据包
    (结论、置信度、证据链、故障码含义、未识别消息)。
    当用户给出日志文件名和测试员记录的时间时使用。

    Args:
        log_file: 日志文件名,例如 case_01_radar_comm_loss.csv
        note_time: 测试员记录的时间,格式 YYYY-MM-DD HH:MM:SS.mmm
    """
    # 安全:LLM 传来的参数不可信。只取文件名部分,防止 "../../.env" 这类路径穿越。
    name = Path(log_file).name
    path = LOG_DIR / name
    if not path.is_file():
        # 出错时把"可用文件"一并返回,模型可以据此自己纠正,而不是卡死
        avail = sorted(p.name for p in LOG_DIR.glob("*.csv") if p.name != "logbook.csv")
        return {"error": f"日志文件不存在: {name}", "available_files": avail}
    try:
        pd.Timestamp(note_time)
    except ValueError:
        return {"error": f"时间格式无法识别: {note_time},请使用 YYYY-MM-DD HH:MM:SS.mmm"}
    return analyze_window(load_dlt_csv(path), note_time)

@tool
def search_knowledge(query: str) -> dict:
    """在 ADAS 知识库中检索故障原因、排查步骤等经验文档。
    需要给出排查建议或解释故障现象时使用;查询词建议包含故障码和现象。

    Args:
        query: 检索问题,例如 "C1A01 雷达通信丢失 排查步骤"
    """
    try:
        results = kb_search(query, k=3)
    except Exception as e:  # 索引未建或 Embedding 服务异常时,回传原因而不是崩溃
        return {"error": f"知识库检索失败: {type(e).__name__}: {e}"}
    if not results:
        return {"results": [], "note": "知识库为空或尚未建立索引(请先运行 python -m scripts.kb build)"}
    return {"results": results}


ALL_TOOLS = [lookup_dtc_tool, analyze_log_window, search_knowledge]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}