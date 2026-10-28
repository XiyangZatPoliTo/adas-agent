from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from BFF_Bot.config import get_setting


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    # 全项目唯一的 LLM 创建入口;模型/Key/地址都不写死在代码里。
    return ChatOpenAI(
        model=get_setting("LLM_MODEL"),
        api_key=get_setting("LLM_API_KEY"),
        base_url=get_setting("LLM_BASE_URL"),  # 换供应商只改 .env
        temperature=temperature,  # 0:根因分析要可复现的结论
    )


def get_embeddings() -> OpenAIEmbeddings:
    """向量化模型的统一入口,与 LLM 共用同一个 Key 和地址。"""
    return OpenAIEmbeddings(
        model=get_setting("EMBED_MODEL"),
        api_key=get_setting("LLM_API_KEY"),
        base_url=get_setting("LLM_BASE_URL"),
        # 关键:LangChain 默认会先把文本切成 token 数组再发送,这是 OpenAI 的做法,
        # 兼容接口通常只接受纯字符串,所以必须关掉,否则会报参数错误。
        check_embedding_ctx_length=False,
        chunk_size=10,  # 单次请求最多 10 条(v4 的批量上限),超过会被拒绝
    )