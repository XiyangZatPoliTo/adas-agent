import pytest


@pytest.fixture(autouse=True)
def _no_kb_threshold(monkeypatch):
    # autouse:对每个测试自动生效。测试必须与本机环境隔离,否则同一份代码在不同电脑上结果不同。
    monkeypatch.delenv("KB_MAX_DISTANCE", raising=False)