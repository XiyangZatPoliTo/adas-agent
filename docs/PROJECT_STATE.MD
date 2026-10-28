# ADAS Agent 项目状态(BFF_Bot)
## 目标
企业 ADAS 功能降级根因分析 Agent:日志分析 + 故障码知识库 + RAG + 工具调用 + LangGraph 编排 + FastAPI。

## 约定
- Python 3.11 + venv;运行 `python -m scripts.xxx`;测试 `pytest -q`(pytest.ini 设了 pythonpath)
- LLM:通义千问(OpenAI 兼容),配置在 .env(LLM_API_KEY / LLM_BASE_URL / LLM_MODEL),统一入口 BFF_Bot/llm.py 的 get_llm()
- 真实样例放 data/raw/(已 gitignore);公开仓库只放模拟数据 data/logs(scripts/generate_sample_log.py 生成,格式与真实 DLT 导出 CSV 同构)

## 目录职责
- BFF_Bot/domain.py 功能状态词表(单一数据源)
- BFF_Bot/loaders/dlt_csv.py 原始 CSV -> 标准结构(不丢行,坏行 parse_ok=False)
- BFF_Bot/analysis/ templates / window / events / chains / pipeline(窗口 -> 新颖性 -> 结构化事件 -> 因果链 -> JSON 证据包)
- config/rules.yaml 事件识别正则(换日志格式只改它)
- BFF_Bot/tools/ dtc.py(故障码查询)、registry.py(给 LLM 的工具)
- BFF_Bot/prompts.py 提示词

## 设计原则
- 事实由规则和数据产出,LLM 只负责解释和表达
- 不丢行、不崩溃、不假装读懂;不确定就降置信度并写明原因
- driver_action 结论必须提示人工看视频确认
- Time 是记录器到达时间(100ms 批次),各 ECU 的 Timestamp 基准不同,不能跨 ECU 比较

## 当前进度
阶段 0~2c 完成(环境、LLM、工具调用、加载层、窗口、规则事件、因果链),27 个测试通过。

## 下一步
LLM 报告生成 -> 版本感知故障码表 -> RAG -> LangGraph -> FastAPI -> README/简历

## 沟通偏好
回复精简;验证只贴一行摘要;日志一句话中英双语;代码带工程师注释