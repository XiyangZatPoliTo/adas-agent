"""演示界面:调用 FastAPI 服务,展示结论、证据链和报告;疑似人为操作时提供人工确认按钮。
Demo UI: a client of the FastAPI service. Any other platform integrates the same way.
"""
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

API = "http://127.0.0.1:8000"
LOGBOOK = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "logs" / "logbook.csv", dtype=str)

st.set_page_config(page_title="BFF Bot", layout="wide")
st.title("BFF Bot · ADAS 功能降级根因分析")

idx = st.sidebar.selectbox("选择案例", list(LOGBOOK.index),
                           format_func=lambda i: f"{LOGBOOK.log_file[i][:7]} | {LOGBOOK.note[i]}")
entry = LOGBOOK.loc[idx]
st.sidebar.caption(f"测试员记录时间: {entry.note_time}")


def call(path: str, payload: dict) -> dict:
    r = httpx.post(API + path, json=payload, timeout=180)
    return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}: {r.text}"}


if st.sidebar.button("开始分析", type="primary"):
    with st.spinner("分析中..."):
        st.session_state["resp"] = call("/analyze", {"log_file": entry.log_file, "note_time": entry.note_time})

resp = st.session_state.get("resp")  # session_state:页面每次交互都会重跑脚本,结果要存在这里

if resp is None:
    st.info("在左侧选择案例并点击「开始分析」")
elif "error" in resp:
    st.error(resp["error"])
else:
    ev = resp.get("evidence") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("结论类型", resp.get("verdict") or "-")
    c2.metric("置信度", resp.get("confidence") or "待人工确认")
    c3.metric("状态", resp["status"])
    st.info(ev.get("summary", ""))

    rows = [e for f in ev.get("findings", []) + ev.get("driver_findings", []) for e in f["evidence"]]
    if rows:
        st.subheader("证据链(按时间)")
        st.dataframe(pd.DataFrame(rows), hide_index=True)

    if resp["status"] == "awaiting_confirmation":
        st.warning(resp["confirmation"]["question"])  # 工作流在这里暂停,等人看视频
        a, b = st.columns(2)
        for col, label, val in ((a, "是,确认为人为操作", True), (b, "否,不是人为操作", False)):
            if col.button(label):
                with st.spinner("生成报告中..."):
                    st.session_state["resp"] = call(f"/analyze/{resp['thread_id']}/confirm", {"confirmed": val})
                st.rerun()
    else:
        st.subheader("分析报告")
        st.markdown(resp["report"])