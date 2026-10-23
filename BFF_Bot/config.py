import os
from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录的 .env 文件


def get_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少环境变量 {name},请检查 .env 文件")
    return value