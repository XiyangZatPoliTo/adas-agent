"""生成通用的示例矩阵(两个版本),用于开发和测试;不含任何真实数据。"""
from pathlib import Path

import pandas as pd

COLS = ["dtc", "fault_name", "diag_module", "maturity_condition", "is_permanent", "category",
        "ACC", "AEB", "LKA", "LDW"]
V1 = [
    ["C1A01", "Front radar link lost", "Radar diag", "link timeout > 500 ms", "yes", "FuSa", "degrade", "degrade", "", ""],
    ["C1A02", "Front camera blocked", "Camera diag", "low image quality > 3 s", "no", "Platform", "", "degrade", "degrade", ""],
    ["C1A03", "Front camera calibration out of range", "Camera diag", "calibration check failed", "yes", "Platform", "degrade", "", "degrade", ""],
]


def write_sample(path) -> None:
    v2 = [r[:] for r in V1]
    v2[0][3] = "link timeout > 300 ms"  # C1A01:成熟条件变严
    v2[1][9] = "degrade"                # C1A02:新增影响 LDW(影响范围变化)
    v2.append(["C1A04", "Front radar blockage suspected", "Radar diag", "detection range reduced > 5 s",
               "no", "Platform", "degrade", "degrade", "", ""])  # 新增故障码
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as w:
        pd.DataFrame(V1, columns=COLS).to_excel(w, sheet_name="v1.0", index=False)
        pd.DataFrame(v2, columns=COLS).to_excel(w, sheet_name="v2.0", index=False)