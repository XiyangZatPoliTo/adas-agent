from langchain_openai import ChatOpenAI

from BFF_Bot.config import get_setting


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=get_setting("LLM_MODEL"),
        api_key=get_setting("LLM_API_KEY"),
        base_url=get_setting("LLM_BASE_URL"),
        temperature=temperature,
    )




