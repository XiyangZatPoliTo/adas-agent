"""故障码矩阵导入:Excel(每个软件版本一个 sheet)-> 标准化的版本化结构。
Import the error code matrix: one sheet per software version -> normalized, versioned structure.
"""
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "matrix_columns.yaml"
MATRIX_JSON = ROOT / "data" / "matrix" / "dtc_matrix.json"
_TRUE = ("yes", "y", "是", "true", "1")


def load_config(path=CONFIG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def import_matrix(xlsx_path, cfg: dict = None) -> dict:
    """返回 {版本: {故障码: 记录}}。版本的顺序 = sheet 的顺序(从旧到新)。"""
    cfg = cfg or load_config()
    cols, funcs = cfg["columns"], cfg["function_columns"]
    # 全部读成字符串、空值保留为 "":避免 pandas 悄悄转成 NaN
    sheets = pd.read_excel(xlsx_path, sheet_name=None, dtype=str, keep_default_na=False)
    out = {}
    for version, df in sheets.items():
        # 快速失败:缺列就明确报错并指出是哪个 sheet,比后面抛 KeyError 好排查
        missing = [c for c in [*cols.values(), *funcs] if c not in df.columns]
        if missing:
            raise ValueError(f"sheet '{version}' 缺少列: {missing}")
        table = {}
        for _, r in df.iterrows():
            code = r[cols["code"]].strip().upper()
            if not code:
                continue  # 跳过空行
            if code in table:
                raise ValueError(f"sheet '{version}' 中故障码重复: {code}")  # 重复多半是录入错误,不能静默覆盖
            table[code] = {
                "name": r[cols["name"]].strip(),
                "module": r[cols["module"]].strip(),
                "maturity": r[cols["maturity"]].strip(),
                "permanent": r[cols["permanent"]].strip().lower() in _TRUE,
                "category": r[cols["category"]].strip(),
                # 不认识的取值标为 unknown,让数据质量问题可见,而不是悄悄当成"无影响"
                "effects": {f: cfg["effect_map"].get(r[f].strip().lower(), "unknown") for f in funcs},
            }
        out[version] = table
    return out


def save_matrix(matrix: dict, path=MATRIX_JSON) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")


def load_matrix(path=MATRIX_JSON) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))