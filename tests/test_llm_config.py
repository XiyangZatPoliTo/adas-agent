from BFF_Bot.llm import get_embeddings


def test_embeddings_config(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost/v1")
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-v4")
    e = get_embeddings()
    assert e.model == "text-embedding-v4"
    assert e.check_embedding_ctx_length is False  # 兼容接口必须关闭
    assert e.chunk_size == 10                      # 不超过批量上限