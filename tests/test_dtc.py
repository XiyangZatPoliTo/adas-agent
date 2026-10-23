from BFF_Bot.tools.dtc import lookup_dtc


def test_lookup_known_code():
    result = lookup_dtc("C1A01")
    assert result["found"] is True
    assert "ACC" in result["affected_functions"]


def test_lookup_is_case_and_space_insensitive():
    assert lookup_dtc("  c1a01  ")["found"] is True


def test_lookup_unknow_code():
    result = lookup_dtc("X9999")
    assert result["found"] is False

