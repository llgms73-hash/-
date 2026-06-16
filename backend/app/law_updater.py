"""
從法務部「全國法規資料庫」官方開放資料 API 下載法規全文，
篩選出與驗屋/房屋交易糾紛相關的法規白名單，並正規化成內部格式存檔。

官方 API: https://law.moj.gov.tw/api/Ch/Law/JSON
回傳值是一個 ZIP 檔，裡面包含 ChLaw.json（全部現行法律）。
"""
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import LAWS_DIR, MOJ_LAW_API_URL, RELEVANT_LAW_NAMES

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HouseInspectionLawBot/1.0; "
        "+https://law.moj.gov.tw/api/)"
    )
}


def _download_chlaw_json(timeout: float = 60.0) -> list[dict[str, Any]]:
    resp = httpx.get(MOJ_LAW_API_URL, headers=HEADERS, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        json_name = next(n for n in zf.namelist() if n.lower().endswith(".json"))
        raw = zf.read(json_name)
    data = json.loads(raw.decode("utf-8-sig"))
    if isinstance(data, dict) and "Laws" in data:
        return data["Laws"]
    if isinstance(data, list):
        return data
    raise ValueError(f"未預期的 ChLaw.json 結構：{type(data)}，請檢查官方 API 是否變更格式")


def _extract_articles(law_raw: dict[str, Any]) -> list[dict[str, str]]:
    """
    嘗試從官方 JSON 物件中取出條文清單。
    官方欄位命名在不同版本可能略有差異，這裡採用多個候選 key 嘗試解析，
    並在完全無法解析時保留原始文字（LawFullContent）做為退路，
    避免索引功能因欄位改名而整個失敗。
    """
    candidates = [
        "LawArticles", "Articles", "LawArticleList", "ArticleList",
    ]
    for key in candidates:
        items = law_raw.get(key)
        if isinstance(items, list) and items:
            articles = []
            for item in items:
                no = (
                    item.get("ArticleNo") or item.get("ArticleNum")
                    or item.get("ArticleNo".lower()) or item.get("No") or ""
                )
                content = (
                    item.get("ArticleContent") or item.get("Content")
                    or item.get("ArticleContext") or ""
                )
                if not content:
                    continue
                articles.append({"no": str(no).strip(), "content": str(content).strip()})
            if articles:
                return articles

    # 退路：整篇法規內容當作單一區塊，仍可被檢索，只是無法精準定位到條號
    full_text = (
        law_raw.get("LawFullContent") or law_raw.get("LawContent")
        or law_raw.get("FullContent") or ""
    )
    if full_text:
        return [{"no": "(全文)", "content": str(full_text).strip()}]
    return []


def update_laws() -> dict[str, Any]:
    """下載並更新白名單內法規，回傳更新摘要（成功/失敗法規名稱）。"""
    raw_laws = _download_chlaw_json()
    by_name = {item.get("LawName", "").strip(): item for item in raw_laws}

    updated, missing, empty = [], [], []
    for name in RELEVANT_LAW_NAMES:
        law_raw = by_name.get(name)
        if law_raw is None:
            missing.append(name)
            continue
        articles = _extract_articles(law_raw)
        if not articles:
            empty.append(name)
            continue

        record = {
            "pcode": law_raw.get("PCode", ""),
            "name": name,
            "last_update": law_raw.get("LawModifiedDate", ""),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "articles": articles,
        }
        out_path = LAWS_DIR / f"{name}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        updated.append(name)

    summary = {"updated": updated, "missing_in_source": missing, "no_articles_parsed": empty}
    logger.info("法規更新完成: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(update_laws(), ensure_ascii=False, indent=2))
