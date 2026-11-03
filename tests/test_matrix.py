import pandas as pd
import pytest

from BFF_Bot.matrix.importer import import_matrix
from BFF_Bot.matrix.query import diff_versions, lookup
from scripts.make_sample_matrix import COLS, write_sample


@pytest.fixture
def matrix(tmp_path):
    p = tmp_path / "m.xlsx"
    write_sample(p)
    return import_matrix(p)


def test_import_normalizes_effects(matrix):
    assert list(matrix) == ["v1.0", "v2.0"]  # 版本顺序 = sheet 顺序
    r = matrix["v1.0"]["C1A01"]
    assert r["effects"] == {"ACC": "degrade", "AEB": "degrade", "LKA": "none", "LDW": "none"}
    assert r["permanent"] is True


def test_missing_column_fails_fast(tmp_path):
    p = tmp_path / "bad.xlsx"
    pd.DataFrame([["C1A01"]], columns=["dtc"]).to_excel(p, index=False)
    with pytest.raises(ValueError, match="缺少列"):
        import_matrix(p)


def test_duplicate_code_rejected(tmp_path):
    p = tmp_path / "dup.xlsx"
    row = ["C1A01", "n", "m", "c", "yes", "FuSa", "degrade", "", "", ""]
    pd.DataFrame([row, row], columns=COLS).to_excel(p, index=False)
    with pytest.raises(ValueError, match="重复"):
        import_matrix(p)


def test_unknown_effect_value_is_visible(tmp_path):
    p = tmp_path / "w.xlsx"
    pd.DataFrame([["C1A01", "n", "m", "c", "yes", "FuSa", "weird", "", "", ""]], columns=COLS).to_excel(p, index=False)
    assert import_matrix(p)["Sheet1"]["C1A01"]["effects"]["ACC"] == "unknown"  # 不悄悄当成 none


def test_lookup_defaults_to_latest_and_supports_version(matrix):
    assert lookup(matrix, "c1a02")["effects"]["LDW"] == "degrade"                 # 默认最新版本 v2.0
    assert lookup(matrix, "C1A02", "v1.0")["effects"]["LDW"] == "none"            # 指定旧版本
    assert lookup(matrix, "C1A02", "v9")["found"] is False                        # 未知版本
    assert lookup(matrix, "X9999")["found"] is False                              # 未知故障码


def test_diff_versions(matrix):
    d = diff_versions(matrix, "v1.0", "v2.0")
    assert d["added"] == ["C1A04"] and d["removed"] == []
    assert d["changed"]["C1A01"] == {"maturity": ("link timeout > 500 ms", "link timeout > 300 ms")}
    assert d["changed"]["C1A02"] == {"effect:LDW": ("none", "degrade")}
    assert "C1A03" not in d["changed"]