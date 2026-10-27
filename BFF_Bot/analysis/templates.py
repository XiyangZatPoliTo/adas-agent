"""消息模板化:把"只有数字不同"的消息归为同一类(日志模板挖掘的最简版)。
Message templating: group messages that differ only by numbers.
"""
import re

# 连续 4 个以上的十六进制字节(空格分隔),如 "24 54 52 49 b2 d0"
_HEXDUMP = re.compile(r"\b(?:[0-9a-fA-F]{2}\s){3,}[0-9a-fA-F]{2}\b")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
# 独立的数字(可带负号和小数)。
# 关键:lookbehind 要求前一个字符不是字母/数字/下划线,
# 这样 "C1A01"、"DTC_C1A01" 这类故障码里的数字会被保留,而 "cycle = 53001" 会被替换。
# 如果不这样做,所有不同的故障码都会被合并成同一个模板,信息就丢了。
_NUM = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?")


def to_template(msg: str) -> str:
    msg = _HEXDUMP.sub("<HEXDUMP>", msg)  # 先处理十六进制转储,避免被当成一堆数字
    msg = _HEX.sub("<HEX>", msg)
    return _NUM.sub("<N>", msg)