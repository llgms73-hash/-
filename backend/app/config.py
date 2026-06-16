import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LAWS_DIR = DATA_DIR / "laws"
CHROMA_DIR = DATA_DIR / "chroma"
MANUAL_DOCS_DIR = DATA_DIR / "manual_docs"

LAWS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
MANUAL_DOCS_DIR.mkdir(parents=True, exist_ok=True)

# 全國法規資料庫官方開放資料 API（法務部）
MOJ_LAW_API_URL = "https://law.moj.gov.tw/api/Ch/Law/JSON"
MOJ_ORDER_API_URL = "https://law.moj.gov.tw/api/Ch/Order/JSON"

# 與「驗屋糾紛 / 房屋交易糾紛」相關的法規白名單（法規全名，需與全國法規資料庫公告名稱一致）
# 之後可依需要增減。White-list 是為了避免索引全部 1萬多部法規造成不必要的雜訊與成本。
RELEVANT_LAW_NAMES = [
    "民法",                      # 物之瑕疵擔保(354~365)、承攬(490~514) 等
    "消費者保護法",
    "公平交易法",
    "平均地權條例",
    "住宅法",
    "建築法",
    "公寓大廈管理條例",
    "不動產經紀業管理條例",
    "不動產估價師法",
    "地籍測量實施規則",
]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")  # 用於保護 /api/admin/update-laws

EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"
)
TOP_K = int(os.environ.get("RAG_TOP_K", "6"))
