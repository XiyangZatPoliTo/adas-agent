"""演示界面(优化版):调用 FastAPI 服务,展示流程进度、结论、证据链、报告;
疑似人为操作时提供人工确认。任何其他平台接入也是同一套接口。
Demo UI (polished): a client of the FastAPI service.
"""
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

API = "http://127.0.0.1:8000"
LOGBOOK = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "logs" / "logbook.csv", dtype=str)

ROLE_LABEL = {"sensor_abnormal": "传感器异常", "dtc_set": "故障码置位", "function_degrade": "功能降级",
              "driver_action": "驾驶员操作", "function_exit": "功能退出"}
# 结论类型 -> (显示名, 颜色对应的 Streamlit 提示框)
VERDICT = {"fault_chain": ("故障链", "error"), "driver_action": ("疑似驾驶员操作，非故障", "info"),
           "unexplained_degrade": ("降级原因不明", "warning"), "inconclusive": ("证据不足，无法判断", "warning")}

st.set_page_config(page_title="BFF Bot", layout="wide")
st.title("BFF Bot · ADAS 功能降级根因分析")
st.caption("演示数据为模拟日志。助手只负责整理证据并给出建议，最终判断由工程师做出。")


def call(path: str, payload: dict) -> dict:
    try:
        r = httpx.post(API + path, json=payload, timeout=180)
    except httpx.HTTPError:
        # 服务没启动时给出可操作的提示,而不是把异常堆栈展示给观众
        return {"error": "无法连接到分析服务。请先双击 start_demo.bat 启动服务。"}
    return r.json() if r.status_code == 200 else {"error": f"请求失败 (HTTP {r.status_code}): {r.text}"}


# ---------- 侧边栏 ----------
st.sidebar.header("操作")
idx = st.sidebar.selectbox("1. 选择案例", list(LOGBOOK.index),
                           format_func=lambda i: f"{LOGBOOK.log_file[i][:7]} | {LOGBOOK.note[i]}")
entry = LOGBOOK.loc[idx]
st.sidebar.info(f"测试员记录\n\n{entry.note}\n\n时间: {entry.note_time}")
if st.sidebar.button("2. 开始分析", type="primary"):
    with st.spinner("分析中..."):
        st.session_state["resp"] = call("/analyze", {"log_file": entry.log_file, "note_time": entry.note_time})

resp = st.session_state.get("resp")  # 页面每次交互都会重跑脚本,结果存在 session_state 里


def show_progress(resp):
    """三步流程指示:已完成 / 进行中 / 未开始。"""
    verdict = (resp or {}).get("verdict")
    mid = {"driver_action": "人工确认", "inconclusive": "跳过检索"}.get(verdict, "检索知识库")
    if resp is None:
        state = ["gray", "gray", "gray"]
    elif resp.get("status") == "awaiting_confirmation":
        state = ["green", "orange", "gray"]
    else:
        state = ["green", "green", "green"]
    for col, color, label in zip(st.columns(3), state, ["① 分析日志", f"② {mid}", "③ 生成报告"]):
        col.markdown(f":{color}[●] **{label}**")


show_progress(resp)
st.divider()

if resp is None:
    st.info("请在左侧选择案例，然后点击「开始分析」。")
elif "error" in resp:
    st.error(resp["error"])
else:
    ev = resp.get("evidence") or {}
    name, kind = VERDICT.get(resp.get("verdict"), (resp.get("verdict") or "-", "info"))
    getattr(st, kind)(f"**{name}**\n\n{ev.get('summary', '')}")  # 按结论类型显示不同颜色
    if resp.get("confidence"):
        st.caption(f"置信度: {resp['confidence']}")

    rows = [{"时间": e["time"], "事件": ROLE_LABEL.get(e["role"], e["role"]), "日志原文": e["text"]}
            for f in ev.get("findings", []) + ev.get("driver_findings", []) for e in f["evidence"]]
    if rows:
        st.subheader("证据链")
        st.dataframe(pd.DataFrame(rows), hide_index=True)

    info = next((f["dtc_info"] for f in ev.get("findings", []) if (f.get("dtc_info") or {}).get("found")), None)
    if info:
        with st.expander(f"故障码详情: {info['code']}"):
            st.write(f"**含义**: {info['description']}")
            st.write(f"**影响功能**: {', '.join(info['affected_functions'])}  |  **严重程度**: {info['severity']}")
            st.write("**常见原因**: " + "; ".join(info["typical_causes"]))
    if ev.get("unclassified_novel"):
        with st.expander("未被规则识别的新消息(供工程师判断)"):
            st.dataframe(pd.DataFrame(ev["unclassified_novel"])[["example", "count", "level"]], hide_index=True)

    if resp["status"] == "awaiting_confirmation":
        st.warning(f"⏸ 流程已暂停，等待人工确认:{resp['confirmation']['question']}")
        a, b = st.columns(2)
        for col, label, val, typ in ((a, "是，确认为人为操作", True, "primary"), (b, "否，不是人为操作", False, "secondary")):
            if col.button(label, type=typ):
                with st.spinner("生成报告中..."):
                    st.session_state["resp"] = call(f"/analyze/{resp['thread_id']}/confirm", {"confirmed": val})
                st.rerun()
    else:
        st.subheader("分析报告")
        with st.container(border=True):
            st.markdown(resp["report"])
        st.download_button("下载报告 (.md)", resp["report"], file_name="analysis_report.md")