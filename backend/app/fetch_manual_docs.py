"""
抓取內政部主管法規共用系統(glrs.moi.gov.tw)上的定型化契約應記載及不得記載事項，
存成 data/manual_docs/*.json，供 RAG 索引使用。

⚠️ 這個網站會擋掉雲端沙盒環境常用的爬蟲 UA，所以這支腳本必須在「你自己的電腦或伺服器」
（網路沒有被擋）執行，不能在本專案開發用的雲端沙盒裡跑。

用法：
    cd backend
    python -m app.fetch_manual_docs

執行後會抓取：
  - 預售屋買賣定型化契約應記載及不得記載事項 (id=FL003296)
  - 成屋買賣定型化契約應記載及不得記載事項   (id=GL000442)

注意：glrs.moi.gov.tw 的 HTML 結構若日後改版，下面的 parse 函式可能要跟著調整。
腳本內建容錯機制：抓不到結構化條文時，會把整段原始文字塞進一筆 "(全文，請人工確認分條)"，
並印出警告，提醒你打開檔案手動檢查、必要時調整 _parse_articles()。
"""
import json
import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.config import MANUAL_DOCS_DIR

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}

DOCS = [
    {
        "name": "預售屋買賣定型化契約應記載及不得記載事項",
        "url": "https://glrs.moi.gov.tw/LawContent.aspx?id=FL003296",
    },
    {
        "name": "成屋買賣定型化契約應記載及不得記載事項",
        "url": "https://glrs.moi.gov.tw/LawContent.aspx?id=GL000442",
    },
]

# 中文數字編號的條列符號，例如「一、」「二十三、」
_ITEM_PATTERN = re.compile(
    r"^([一二三四五六七八九十百]+)、\s*(.+)$"
)


def _split_into_items(section_text: str) -> list[dict[str, str]]:
    """把一段條列文字依「一、二、三...」切成多筆條文。"""
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    items: list[dict[str, str]] = []
    current_no, current_buf = None, []

    def flush():
        if current_no is not None and current_buf:
            items.append({"no": current_no, "content": "\n".join(current_buf).strip()})

    for line in lines:
        m = _ITEM_PATTERN.match(line)
        if m:
            flush()
            current_no, current_buf = m.group(1), [m.group(2)]
        else:
            current_buf.append(line)
    flush()
    return items


def _parse_articles(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    full_text = soup.get_text("\n")

    # glrs.moi.gov.tw 慣例：先列「應記載事項」整段，再列「不得記載事項」整段
    split_idx = full_text.find("不得記載事項")
    if split_idx == -1:
        logger.warning("找不到「不得記載事項」標題，無法切分應記載/不得記載，將整段視為單一全文")
        return [{"no": "(全文，請人工確認分條)", "content": full_text.strip()}]

    required_text = full_text[:split_idx]
    prohibited_text = full_text[split_idx:]

    required_items = _split_into_items(required_text)
    prohibited_items = _split_into_items(prohibited_text)

    articles = [{"no": f"應記載事項{it['no']}", "content": it["content"]} for it in required_items]
    articles += [{"no": f"不得記載事項{it['no']}", "content": it["content"]} for it in prohibited_items]

    if not articles:
        logger.warning("條文切分結果為空，將整段視為單一全文，請打開檔案人工確認")
        return [{"no": "(全文，請人工確認分條)", "content": full_text.strip()}]

    return articles


def fetch_one(name: str, url: str) -> dict:
    resp = httpx.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    articles = _parse_articles(resp.text)

    record = {
        "name": name,
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }
    out_path = MANUAL_DOCS_DIR / f"{name}.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已存檔 %s（%d 筆條文）-> %s", name, len(articles), out_path)
    return record


def main():
    for doc in DOCS:
        try:
            record = fetch_one(doc["name"], doc["url"])
            if any(a["no"].startswith("(全文") for a in record["articles"]):
                print(f"⚠️  {doc['name']}：自動分條失敗，請打開 data/manual_docs/{doc['name']}.json 人工檢查、手動分條。")
            else:
                print(f"✅ {doc['name']}：抓取成功，共 {len(record['articles'])} 筆條文。")
        except Exception as e:  # noqa: BLE001
            print(f"❌ {doc['name']} 抓取失敗：{e}")
            logger.exception("抓取 %s 失敗", doc["name"])

    print("\n完成後請務必打開檔案核對內容是否正確、是否為最新版本，再執行：")
    print("    python -m app.build_index")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
