"""生成 DLT 导出风格的模拟日志(演示数据,非真实车辆数据;ECU/模块名均为虚构)。
Generate DLT-export-style simulated logs (demo data; ECU/module names are fictional).
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from BFF_Bot.domain import ACTIVATE, DEACTIVATE, DEGRADE

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
START = datetime(2026, 1, 15, 14, 0, 0)
DURATION_S = 120   # 连续记录 2 分钟
FLUSH_MS = 100     # 记录器每 100ms 批量落盘一次 -> Time(到达时间)按批对齐

# 固定随机种子:数据可复现,便于测试和问题复盘。
rng = random.Random(42)

# 各 ECU 的计时器基准(秒):真实日志里各 ECU 计时器互不相同,这里复现这一点。
ECU_BASE = {"PRC1": 51.0, "CTL1": 2130.0, "GWY1": 14725.0}
FUNCS = ["ACC", "LKA", "AEB"]
BIN_IDS = [21, 1100, 1600, 5200, 120010]  # 虚构的二进制消息 ID
CAMERA_QUALITY = {"OK": (90, 99), "Blocked": (3, 10), "CalibError": (88, 97)}
# 窗口打印时用的关键字(仅用于肉眼检查,真正的解析规则在后续的规则配置里)
KEY_RE = r"DTC set|state change|State=|button =|brightness|status = (?!OK)"


def row(t_ms, ecu, app, ctx, level, payload, mode="verbose", nargs=1, type_="log"):
    """一条"原始事件"。t_ms = 事件在日志内的发生时刻(毫秒)。"""
    return dict(t_ms=t_ms, ecu=ecu, app=app, ctx=ctx, type=type_, level=level,
                mode=mode, nargs=nargs, payload=payload)


def init_state_msg(func):
    # 各功能模块措辞风格不统一(AEB 用分号风格),模拟真实日志的不规整。
    return f"Aeb;State={ACTIVATE}" if func == "AEB" else f"{func.title()} : state = {ACTIVATE}"


def change_msg(func, new, reason):
    if func == "AEB":
        return f"Aeb;State={new};Reason={reason}"
    return f"{func.title()} : state change {ACTIVATE} -> {new} , reason = {reason}"


def sensor_text(sensor, status, t, start_ms):
    if sensor == "RADAR":
        lost = 0 if status == "OK" else (t - start_ms) // 50
        return f"Rdr : link status = {status} , lost_frames = {lost}"
    lo, hi = CAMERA_QUALITY[status]
    return f"Cam : image status = {status} , quality = {rng.randint(lo, hi)}"


def binary_row(t_ms):
    """二进制行:'[消息ID] 乱码|十六进制字节'。ASCII 部分是乱码,需要描述文件才能解码。"""
    mid, n = rng.choice(BIN_IDS), rng.randint(12, 48)
    ascii_part = "".join(rng.choice("-----ts9hl4Fr") for _ in range(n))
    hex_part = " ".join(f"{rng.randrange(256):02x}" for _ in range(n))
    payload = f"[{mid}] {ascii_part}|{hex_part}"
    if rng.random() < 0.7:  # 真实日志里很多二进制行没有 Apid/Ctid/Type/Subtype
        return row(t_ms, "GWY1", "", "", "", payload, mode="non-verbose", nargs=0, type_="")
    return row(t_ms, "GWY1", "GWAY", "Raw", "debug", payload, mode="non-verbose", nargs=0)


def noise_rows(sensor_faults):
    """背景噪声:占日志绝大多数。真实故障证据淹没在这里面。"""
    rows, end = [], DURATION_S * 1000
    for func in FUNCS:
        rows.append(row(0, "CTL1", "FUNC", func, "info", init_state_msg(func)))
    for t in range(0, end, 40):  # 调度器 error 级消息,周期性重复:error 不等于故障
        rows.append(row(t, "CTL1", "SCHD", "Sched", "error", "Sched : CycleStart - tick", nargs=3))
    cycle = 53000
    for t in range(0, end, 100):
        cycle += 1
        rows.append(row(t, "CTL1", "SCHD", "Alive", "warn",
                        f"Alive : app = ctl , cycle = {cycle} , events = 0", nargs=8))
        rows.append(binary_row(t + 5))
    for t in range(0, end, 50):  # IMU 风格数据流
        rows.append(row(t, "PRC1", "PERC", "Imu", "info",
                        f"EventID: 05 | imu - {t // 50} | $XIMU,{t},{rng.gauss(0, 0.02):.6f},"
                        f"{rng.gauss(0, 0.02):.6f},{9.8 + rng.gauss(0, 0.05):.6f}", nargs=7))
    speed = 80.0
    for t in range(0, end, 200):  # 车速:这个模块用分号分隔
        speed = min(max(speed + rng.gauss(0, 0.3), 60.0), 110.0)
        rows.append(row(t, "CTL1", "VEH", "Veh",
                        "info", f"Veh : speed = {speed:.1f} kmh ; gear = D ; steer = {rng.gauss(0, 1.5):.1f}"))
    for t in range(0, end, 1000):  # 传感器链路 1Hz;故障开始后改为异常状态
        for offset, sensor, app, ctx in ((20, "RADAR", "RDR", "Link"), (40, "CAMERA", "CAM", "Img")):
            start_ms, status = sensor_faults.get(sensor, (None, "OK"))
            cur = status if start_ms is not None and t >= start_ms else "OK"
            rows.append(row(t + offset, "PRC1", app, ctx, "info",
                            sensor_text(sensor, cur, t, start_ms or 0), nargs=2))
    for t in range(0, end, 10_000):  # 控制响应
        rows.append(row(t + 3, "GWY1", "", "", "response", "[ ok] 00 00 00 06",
                        mode="non-verbose", nargs=0, type_="control"))
    return rows


def fault_rows(f):
    """故障因果链:传感器异常 -> 成熟时间 -> DTC 置位 -> 150ms 后功能降级。"""
    dtc_ms = f["start_ms"] + f["mature_ms"]
    rows = [row(dtc_ms, "CTL1", "DIAG", "Dtc", "warn",
                f"Diag : DTC set , code = {f['dtc']} , status = confirmed", nargs=3)]
    for func in f["funcs"]:
        rows.append(row(dtc_ms + 150, "CTL1", "FUNC", func, "info",
                        change_msg(func, DEGRADE, f"DTC_{f['dtc']}")))
    return rows


# 与 data/dtc_table.json 保持一致(故障码、受影响功能)。
CASES = {
    "case_01_radar_comm_loss": dict(
        fault=dict(sensor="RADAR", start_ms=70_000, status="CommLost",
                   dtc="C1A01", mature_ms=500, funcs=["ACC", "AEB"]),
        # 干扰项:窗口里出现的、与故障无关但"新出现"的消息
        decoys=[(72_000, "Hmi : screen brightness changed , level = 3")],
        note_ms=74_000, note="ACC 突然降级,仪表有提示 / ACC suddenly degraded",
    ),
    "case_02_camera_blocked": dict(
        fault=dict(sensor="CAMERA", start_ms=45_000, status="Blocked",
                   dtc="C1A02", mature_ms=3_000, funcs=["LKA", "AEB"]),
        note_ms=52_000, note="车道保持功能不可用 / LKA unavailable",
    ),
    "case_03_camera_calib_error": dict(
        fault=dict(sensor="CAMERA", start_ms=5_000, status="CalibError",
                   dtc="C1A03", mature_ms=1_000, funcs=["LKA", "ACC"]),
        note_ms=15_000, note="启动后 LKA 与 ACC 均不可用 / LKA and ACC unavailable after start",
    ),
    # 反例:人为操作,不是故障。
    "case_04_driver_cancel_acc": dict(
        fault=None, driver_cancel_ms=60_000,
        note_ms=61_500, note="ACC 突然退出 / ACC suddenly exited",
    ),
}


def fmt(ms):
    """日志内毫秒偏移 -> 完整的 ISO 时间字符串(毫秒精度),避免再被截断。"""
    return (START + timedelta(milliseconds=ms)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def build_case(cfg):
    """返回与真实 DLT 导出同列同序的 DataFrame。"""
    fault = cfg.get("fault")
    sensor_faults = {fault["sensor"]: (fault["start_ms"], fault["status"])} if fault else {}
    rows = noise_rows(sensor_faults)
    if fault:
        rows += fault_rows(fault)
    else:
        c = cfg["driver_cancel_ms"]
        rows.append(row(c, "CTL1", "HMI", "Btn", "info", "Hmi : button = ACC_cancel ; source = steering_wheel"))
        rows.append(row(c + 80, "CTL1", "FUNC", "ACC", "info", change_msg("ACC", DEACTIVATE, "driver_request")))
    for t, text in cfg.get("decoys", []):
        rows.append(row(t, "CTL1", "HMI", "Disp", "info", text))

    df = pd.DataFrame(rows).sort_values("t_ms", kind="stable").reset_index(drop=True)
    # Count:每个 ECU 自己的 8 位计数器(0~255 循环),按发生顺序递增
    df["Count"] = df.groupby("ecu").cumcount() % 256
    # Timestamp:ECU 自己的计时器;网关 ECU 约 80% 的行为 0(没有有效时间戳)
    df["Timestamp"] = [0 if (e == "GWY1" and rng.random() < 0.8) else round(ECU_BASE[e] + t / 1000, 4)
                       for e, t in zip(df["ecu"], df["t_ms"])]
    # Time:记录器"到达时间",向上对齐到 100ms 批次,所以同一批的 Time 相同
    arrival = (df["t_ms"] // FLUSH_MS + 1) * FLUSH_MS
    df["Time"] = [fmt(int(a)) for a in arrival]
    df["arrival"] = arrival
    df = df.sort_values(["arrival", "t_ms"], kind="stable").reset_index(drop=True)
    df["Index"] = range(len(df))
    df["SessionId"] = 0
    return df.rename(columns={"ecu": "Ecuid", "app": "Apid", "ctx": "Ctid", "type": "Type",
                              "level": "Subtype", "mode": "Mode", "nargs": "#Args", "payload": "Payload"})[
        ["Index", "Time", "Timestamp", "Count", "Ecuid", "Apid", "Ctid", "SessionId",
         "Type", "Subtype", "Mode", "#Args", "Payload"]]


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logbook = []
    for name, cfg in CASES.items():
        out = build_case(cfg)
        out.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8")
        logbook.append({"log_file": f"{name}.csv", "note_time": fmt(cfg["note_ms"]), "note": cfg["note"]})

        # 模拟真实排查:以 logbook 时间为中心取窗口,只看含关键字的行(肉眼检查)
        lo, hi = fmt(max(cfg["note_ms"] - 12_000, 0)), fmt(cfg["note_ms"] + 1_000)
        win = out[out["Time"].between(lo, hi) & out["Payload"].str.contains(KEY_RE)]
        print(f"\n=== {name}: 共 {len(out)} 行,各 ECU 行数 {out['Ecuid'].value_counts().to_dict()},"
              f"logbook 时间 {fmt(cfg['note_ms'])} ===")
        print(win[["Time", "Ecuid", "Subtype", "Payload"]].to_string(index=False))

    pd.DataFrame(logbook).to_csv(OUT_DIR / "logbook.csv", index=False, encoding="utf-8")
    print("\nlogbook.csv 已生成")