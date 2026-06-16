"""向量索引：把法規條文切成 chunk、embed 後存進本地 Chroma DB，並提供檢索功能。"""
import json
import logging
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_DIR, EMBEDDING_MODEL_NAME, LAWS_DIR, MANUAL_DOCS_DIR, TOP_K

logger = logging.getLogger(__name__)

COLLECTION_NAME = "house_inspection_laws"

_model: SentenceTransformer | None = None
_client = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def _iter_documents() -> list[dict[str, Any]]:
    docs = []
    for folder in (LAWS_DIR, MANUAL_DOCS_DIR):
        for path in folder.glob("*.json"):
            try:
                docs.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                logger.warning("略過無法解析的檔案: %s", path)
    return docs


def build_index() -> int:
    """重新建立整個向量索引，回傳已索引的條文數量。"""
    collection = _get_collection()
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    model = _get_model()
    ids, texts, metadatas = [], [], []
    for doc in _iter_documents():
        law_name = doc.get("name", "未命名法規")
        for i, article in enumerate(doc.get("articles", [])):
            no = article.get("no", str(i))
            content = article.get("content", "").strip()
            if not content:
                continue
            ids.append(f"{law_name}::{no}")
            texts.append(f"《{law_name}》第{no}條\n{content}")
            metadatas.append({"law_name": law_name, "article_no": no})

    if not texts:
        logger.warning("沒有任何條文可索引，請先執行 app.law_updater 下載法規。")
        return 0

    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    logger.info("已索引 %d 筆條文", len(texts))
    return len(texts)


def search(query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    model = _get_model()
    query_embedding = model.encode([query]).tolist()
    result = collection.query(query_embeddings=query_embedding, n_results=min(top_k, collection.count()))
    hits = []
    for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({"text": doc, "law_name": meta["law_name"], "article_no": meta["article_no"], "distance": dist})
    return hits


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_index()
