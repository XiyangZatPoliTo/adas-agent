"""知识库:文档加载 -> 切块 -> 向量库 -> 检索。
Knowledge base: load -> chunk -> vector store -> retrieval.
"""
import re
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from BFF_Bot.llm import get_embeddings

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"
INDEX_DIR = ROOT / "data" / "index"  # 向量库的持久化目录(生成物,已 gitignore)
COLLECTION = "adas_kb"


def load_documents(directory=KNOWLEDGE_DIR) -> list[Document]:
    docs = []
    for p in sorted(Path(directory).glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.search(r"^故障码:\s*(.+)$", text, re.M)
        codes = [c.strip() for c in re.split(r"[,,]", m.group(1))] if m else []
        # Chroma 的元数据值只能是 str/int/float/bool,不能是列表,所以故障码拼成字符串
        docs.append(Document(page_content=text, metadata={"source": p.name, "dtcs": ",".join(codes)}))
    return docs


def split_documents(docs: list[Document]) -> list[Document]:
    # 优先在二级标题处切开,其次段落、句子;块之间留 50 字重叠,避免语义被硬切断
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300, chunk_overlap=50, separators=["\n## ", "\n\n", "\n", "。", " ", ""])
    chunks = []
    for d in docs:
        title = d.page_content.splitlines()[0].lstrip("# ").strip()
        for piece in splitter.split_text(d.page_content):
            # 每个块前加上文档标题:否则"## 可能原因"这种块脱离上下文后,
            # 检索时无法知道它说的是哪个故障
            chunks.append(Document(page_content=f"[{title}] {piece}", metadata=dict(d.metadata)))
    return chunks


def build_index(docs=None, persist_dir=INDEX_DIR, embeddings=None) -> Chroma:
    # 知识库很小,每次全量重建最简单可靠;规模大了再做增量更新
    shutil.rmtree(persist_dir, ignore_errors=True)
    chunks = split_documents(docs if docs is not None else load_documents())
    return Chroma.from_documents(chunks, embeddings or get_embeddings(),
                                 collection_name=COLLECTION, persist_directory=str(persist_dir))


def load_store(persist_dir=INDEX_DIR, embeddings=None) -> Chroma:
    return Chroma(collection_name=COLLECTION, embedding_function=embeddings or get_embeddings(),
                  persist_directory=str(persist_dir))


def search(query: str, k: int = 3, store=None) -> list[dict]:
    """返回 JSON 友好的检索结果。distance 越小越相关。"""
    store = store or load_store()
    return [{"source": d.metadata["source"], "distance": round(float(s), 3), "text": d.page_content}
            for d, s in store.similarity_search_with_score(query, k=k)]