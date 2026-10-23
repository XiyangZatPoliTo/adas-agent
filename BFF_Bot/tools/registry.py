from langchain_core.tools import tool

from BFF_Bot.tools.dtc import lookup_dtc


@tool
def lookup_dtc_tool(code: str) -> dict:
    """查询 ADAS 故障码(DTC)的含义、受影响的功能、严重程度和常见原因。
    当用户提到类似 C1A01、U0100 这样的故障码时使用。

    Args:
        code: 故障码,例如 C1A01
    """
    return lookup_dtc(code)

ALL_TOOLS = [lookup_dtc_tool]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}