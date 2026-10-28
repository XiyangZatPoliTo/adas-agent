from langchain_core.embeddings import DeterministicFakeEmbedding

from BFF_Bot.rag.store import build_index, load_documents, search, split_documents

DOC = "# 测试文档\n故障码: C1A02, C1A03\n\n## 现象\n图像质量下降。\n\n## 可能原因\n玻璃结冰。\n"


def make_docs(tmp_path):
    (tmp_path / "a.md").write_text(DOC, encoding="utf-8")
    return load_documents(tmp_path)


def test_load_documents_parses_dtc_codes(tmp_path):
    assert make_docs(tmp_path)[0].metadata == {"source": "a.md", "dtcs": "C1A02,C1A03"}


def test_chunks_carry_title_and_metadata(tmp_path):
    chunks = split_documents(make_docs(tmp_path))
    assert chunks and all(c.page_content.startswith("[测试文档]") for c in chunks)
    assert all(c.metadata["source"] == "a.md" for c in chunks)


def test_index_roundtrip_with_fake_embeddings(tmp_path):
    emb = DeterministicFakeEmbedding(size=32)  # 相同文本 -> 相同向量,用于验证"存取链路"
    docs = make_docs(tmp_path)
    store = build_index(docs, persist_dir=tmp_path / "idx", embeddings=emb)
    target = split_documents(docs)[0].page_content
    top = search(target, k=1, store=store)[0]
    assert top["text"] == target and top["source"] == "a.md"