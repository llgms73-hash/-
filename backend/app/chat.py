"""把使用者問題 + 檢索到的法條丟給 Claude，產生附法源依據的回覆。"""
from anthropic import Anthropic

from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from app.rag import search

SYSTEM_PROMPT = """\
你是「驗屋糾紛 AI 法律幫手」，協助使用者理解驗屋、房屋交易（預售屋/成屋）相關的法律問題。

規則：
1. 只根據下方提供的【參考法條】內容回答，禁止引用未提供的法條或臆測法條內容。
2. 若參考法條不足以回答問題，要明確告知使用者「現有資料庫法條不足以完整回答」，並建議洽詢律師或地方政府消費者保護官/不動產糾紛調處委員會。
3. 回答時要清楚標示引用了哪一條（例如：依《民法》第354條...）。
4. 結尾必須加上提醒：「以上內容為一般法律資訊，非正式法律意見，具體案件請洽律師或相關主管機關。」
5. 用繁體中文、白話但精確地回答，避免過度冗長。
"""


def answer_question(question: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("尚未設定 ANTHROPIC_API_KEY 環境變數")

    hits = search(question)
    if hits:
        context = "\n\n".join(f"[{i+1}] {h['text']}" for i, h in enumerate(hits))
    else:
        context = "(目前向量索引中沒有任何法條，請先執行 python -m app.build_index 建立索引)"

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"【參考法條】\n{context}\n\n【使用者問題】\n{question}",
            }
        ],
    )
    reply_text = "".join(block.text for block in message.content if block.type == "text")
    sources = [{"law_name": h["law_name"], "article_no": h["article_no"]} for h in hits]
    return {"answer": reply_text, "sources": sources}
