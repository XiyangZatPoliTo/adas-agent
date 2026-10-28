import argparse

from BFF_Bot.agent.simple_agent import run_agent
from BFF_Bot.prompts import REPORT_SYSTEM_PROMPT

DEFAULT_Q = "日志 case_01_radar_comm_loss.csv 中,测试员在 2026-01-15 14:01:14.000 记录 ACC 突然降级,请分析根因。"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default=DEFAULT_Q)
    print(run_agent(parser.parse_args().question, REPORT_SYSTEM_PROMPT))