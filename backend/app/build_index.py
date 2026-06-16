"""CLI: 重新建立向量索引。用法: python -m app.build_index"""
import logging

from app.rag import build_index

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = build_index()
    print(f"索引完成，共 {count} 筆條文。")
