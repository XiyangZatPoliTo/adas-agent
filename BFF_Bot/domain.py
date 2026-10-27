# 功能状态词表:全项目唯一定义处(single source of truth)。
# 真实词表需要 double check,确认后只改这里,
# 生成器、解析器、分析工具都会自动跟着变。
ACTIVATE = "Activate"
DEACTIVATE = "Deactivate"
STANDBY = "Standby"
DEGRADE = "Degrade"
OFF = "Off"

FUNCTION_STATES = (ACTIVATE, DEACTIVATE, STANDBY, DEGRADE, OFF)