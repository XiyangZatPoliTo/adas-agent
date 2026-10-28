"""因果链组装:把结构化事件串成"传感器异常 -> DTC -> 功能降级"的证据链,并给出置信度。
Assemble structured events into evidence chains with confidence levels.
原则:规则只处理能确定的部分;不确定就降低置信度并写明原因,绝不硬给结论。
"""
import pandas as pd

from BFF_Bot.domain import DEACTIVATE, DEGRADE, OFF
from BFF_Bot.tools.dtc import lookup_dtc

SENSOR_TO_DTC_MAX_S = 10.0  # 传感器异常到 DTC 置位允许的最大间隔
ORDER_TOLERANCE_S = 0.2     # 顺序容差:Time 是 100ms 批量到达时间,同批内先后不可靠
DRIVER_LEAD_S = 1.0         # 驾驶员操作应发生在功能退出之前不超过这么久

TOL = pd.Timedelta(seconds=ORDER_TOLERANCE_S)
LAG = pd.Timedelta(seconds=SENSOR_TO_DTC_MAX_S)
LEAD = pd.Timedelta(seconds=DRIVER_LEAD_S)
LEVELS = ["low", "medium", "high"]  # 下标即等级,方便用 min() 做"封顶"
RANK = {"low": 0, "medium": 1, "high": 2}
ROLE_ORDER = {"sensor_abnormal": 0, "dtc_set": 1, "function_degrade": 2}  # 同一时刻按因果顺序排


def _ts(t) -> str:
    return t.strftime("%H:%M:%S.%f")[:-3]


def _evidence(r, role: str) -> dict:
    return {"time": _ts(r.wall_time), "ecu": r.ecu, "role": role, "text": r.text}


def _dtc_finding(code, degrade_rows, dtc_rows, sensor_rows) -> dict:
    """围绕一个 DTC 组装证据链:传感器异常 -> DTC 置位 -> 功能降级。"""
    first_deg = min(degrade_rows, key=lambda r: r.wall_time)
    same = [r for r in dtc_rows if r.fields["code"].upper() == code]
    before = [r for r in same if r.wall_time <= first_deg.wall_time + TOL]  # 允许批内顺序误差
    late = [r for r in same if r.wall_time > first_deg.wall_time + TOL]
    dtc_ev = min(before, key=lambda r: r.wall_time) if before else None

    level, reasoning, evidence = 2, [], []  # 从"高"开始,遇到疑点就往下扣
    if dtc_ev is None:
        level = 0
        reasoning.append(f"DTC {code} 在功能降级之后才置位,因果顺序存疑" if late else
                         f"降级消息引用了 DTC_{code},但窗口内没有对应的置位事件(可能在窗口之前,或消息缺失/损坏)")
    else:
        reasoning.append(f"DTC {code} 置位后功能降级,且降级消息明确引用该 DTC")
        evidence.append(_evidence(dtc_ev, "dtc_set"))

    # 传感器证据:每个传感器取"最早的异常",必须先于参照时刻且间隔不超过 LAG
    anchor = dtc_ev or first_deg
    cand = {}
    for r in sorted(sensor_rows, key=lambda r: r.wall_time):
        s = r.fields["sensor"]
        if s not in cand and r.wall_time <= anchor.wall_time + TOL and anchor.wall_time - r.wall_time <= LAG:
            cand[s] = r
    if cand:
        reasoning.append(f"先于{'DTC' if dtc_ev else '降级'}出现异常的传感器: {', '.join(sorted(cand))}")
        evidence += [_evidence(r, "sensor_abnormal") for r in cand.values()]
        if len(cand) > 1:
            level = min(level, 1)
            reasoning.append("多个传感器几乎同时异常,无法仅凭日志确定谁是源头,需人工判断")
    elif dtc_ev is not None:
        level = min(level, 1)
        reasoning.append("窗口内没有找到先于 DTC 的传感器异常,缺少传感器层面的证据")
    evidence += [_evidence(r, "function_degrade") for r in degrade_rows]
    evidence.sort(key=lambda e: (e["time"], ROLE_ORDER[e["role"]]))

    # 用确定性的故障码表交叉核对:事实来自数据,不来自 LLM
    info = lookup_dtc(code)
    logged = sorted({r.fields["func"].upper() for r in degrade_rows})
    consistent, unobserved = None, []
    if info["found"]:
        expected = set(info["affected_functions"])
        consistent = set(logged) <= expected  # 日志里降级的功能都在表里 -> 一致
        unobserved = sorted(expected - set(logged))  # 表里有、日志没看到:仅提示,不扣分
        if not consistent:
            level = min(level, 1)
            reasoning.append(f"日志中降级的功能 {logged} 超出故障码表的受影响功能 {sorted(expected)},请核对规则或软件版本")
        if unobserved:
            reasoning.append(f"表中还列出 {unobserved},但窗口内未见其降级消息(可能日志未覆盖该功能)")
    else:
        reasoning.append(f"故障码 {code} 不在知识表中,无法核对其含义")

    return {"dtc": code, "dtc_info": info, "degraded_functions": logged, "sensor_evidence": sorted(cand),
            "consistent_with_dtc_table": consistent, "unobserved_functions": unobserved,
            "confidence": LEVELS[level], "reasoning": reasoning, "evidence": evidence}


def _orphan_finding(rows) -> dict:
    """功能降级了,但消息里没有引用任何 DTC:原因不明,只如实报告。"""
    return {"dtc": None, "dtc_info": None, "degraded_functions": sorted({r.fields["func"].upper() for r in rows}),
            "sensor_evidence": [], "consistent_with_dtc_table": None, "unobserved_functions": [],
            "confidence": "low", "reasoning": ["功能降级消息没有引用 DTC,窗口内无法确定原因"],
            "evidence": [_evidence(r, "function_degrade") for r in rows]}


def _driver_findings(exit_rows, driver_rows) -> list:
    out = []
    for r in exit_rows:
        if r.fields.get("reason", "").lower() != "driver_request":
            continue
        func = r.fields["func"]
        # 驾驶员按键应在功能退出之前(含批内容差),且按键名与功能名对应(如 ACC_cancel <-> Acc)
        acts = [d for d in driver_rows if d.fields["button"].lower().startswith(func.lower())
                and -TOL <= (r.wall_time - d.wall_time) <= LEAD]
        reasoning = ([f"驾驶员操作 {acts[0].fields['button']} 后 {func.upper()} 退出,退出原因为 driver_request"] if acts else
                     ["退出原因为 driver_request,但窗口内没有对应的按键事件"])
        reasoning.append("按流程仍需对照视频确认,排除误判")
        out.append({"function": func.upper(), "confidence": "high" if acts else "medium",
                    "needs_human_confirmation": True, "reasoning": reasoning,
                    "evidence": [_evidence(d, "driver_action") for d in acts] + [_evidence(r, "function_exit")]})
    return out


def build_findings(events: pd.DataFrame, baseline_ok: bool = True) -> dict:
    rows = list(events.itertuples())  # 用普通列表处理,空输入也不会出边界问题
    dtc_rows = [r for r in rows if r.category == "dtc_set"]
    sensor_rows = [r for r in rows if r.category == "sensor_status" and r.abnormal]
    driver_rows = [r for r in rows if r.category == "driver_action"]
    func_rows = [r for r in rows if r.category == "function_state"]
    # 状态比较一律忽略大小写,真实词表确认后只需改 domain.py
    degrades = [r for r in func_rows if r.fields["state"].lower() == DEGRADE.lower()]
    exits = [r for r in func_rows if r.fields["state"].lower() in (DEACTIVATE.lower(), OFF.lower())]

    notes = []
    if not baseline_ok:
        notes.append("基线过短(故障发生在日志开头附近),'新出现'的判断可信度较低")

    by_code, orphans = {}, []
    for r in degrades:
        reason = r.fields.get("reason", "")
        if reason.upper().startswith("DTC_"):  # 降级消息明确引用了某个 DTC
            by_code.setdefault(reason[4:].upper(), []).append(r)
        else:
            orphans.append(r)
    findings = [_dtc_finding(c, frs, dtc_rows, sensor_rows) for c, frs in by_code.items()]
    if orphans:
        findings.append(_orphan_finding(orphans))
    driver_findings = _driver_findings(exits, driver_rows)

    fault = [f for f in findings if f["dtc"]]
    if fault:
        best = max(fault, key=lambda f: RANK[f["confidence"]])
        parts = ([f"传感器异常({', '.join(best['sensor_evidence'])})"] if best["sensor_evidence"] else []) + \
                [f"DTC {best['dtc']}", f"{', '.join(best['degraded_functions'])} 降级"]
        verdict, conf, summary = "fault_chain", best["confidence"], "故障链: " + " -> ".join(parts)
    elif findings:
        verdict, conf, summary = "unexplained_degrade", "low", "功能降级,但日志中没有引用任何 DTC,原因不明"
    elif driver_findings:
        best = max(driver_findings, key=lambda f: RANK[f["confidence"]])
        verdict, conf = "driver_action", best["confidence"]
        summary = f"{best['function']} 由驾驶员操作退出,疑似非故障(需对照视频确认)"
    else:
        verdict, conf, summary = "inconclusive", "low", "窗口内未识别到与降级相关的事件"
        notes.append("可能原因:规则未覆盖该日志格式、logbook 时间不准、关键消息缺失或损坏、故障发生在窗口之前。"
                     "建议扩大窗口,并查看未被规则识别的新模板")
    if fault and driver_findings:
        notes.append("窗口内同时存在驾驶员操作与故障事件,需人工确认")
    return {"verdict": verdict, "confidence": conf, "summary": f"{summary} (置信度 {conf})",
            "findings": findings, "driver_findings": driver_findings, "notes": notes}