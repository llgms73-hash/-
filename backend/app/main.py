import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.chat import answer_question
from app.config import ADMIN_TOKEN, BASE_DIR
from app.law_updater import update_laws
from app.rag import build_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="驗屋糾紛 AI 法律幫手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "question 不可為空")
    try:
        return answer_question(question)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


def _check_admin(token: str | None):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(401, "未授權")


@app.post("/api/admin/update-laws")
def admin_update_laws(x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    summary = update_laws()
    indexed_count = build_index()
    return {"law_update": summary, "indexed_chunks": indexed_count}


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _scheduled_update_job():
    logger.info("執行排程法規更新...")
    try:
        update_laws()
        build_index()
        logger.info("排程法規更新完成")
    except Exception:
        logger.exception("排程法規更新失敗")


scheduler = BackgroundScheduler()
# 預設每週日凌晨 3 點自動檢查法規更新一次
scheduler.add_job(_scheduled_update_job, "cron", day_of_week="sun", hour=3)


@app.on_event("startup")
def on_startup():
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown(wait=False)


# 在容器裡 frontend 會被 COPY 到 /code/frontend（Dockerfile 定義），
# 本機開發時 frontend 在 backend 的上層目錄，兩個路徑都試一次
for _frontend_candidate in [
    BASE_DIR / "frontend",        # 容器路徑 /code/frontend
    BASE_DIR.parent / "frontend", # 本機路徑 ../frontend
]:
    if _frontend_candidate.exists():
        app.mount("/", StaticFiles(directory=str(_frontend_candidate), html=True), name="frontend")
        break
