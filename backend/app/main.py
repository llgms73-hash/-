import io
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.chat import answer_question
from app.config import ADMIN_TOKEN, BASE_DIR
from app.interior_design import (
    COLOR_PALETTES,
    DESIGN_STYLES,
    MATERIALS,
    analyze_room,
    build_prompt,
    generate_image,
)
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


# ── Interior Design API ──────────────────────────────────────────────────────

@app.get("/api/design/options")
def design_options():
    """Return available styles, palettes, and materials."""
    return {"styles": DESIGN_STYLES, "palettes": COLOR_PALETTES, "materials": MATERIALS}


@app.post("/api/design/analyze")
async def design_analyze(file: UploadFile = File(...)):
    """Analyze uploaded room photo with Claude Vision."""
    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(400, "圖片太大，請上傳 20 MB 以下的圖片")
    result = await analyze_room(image_bytes, file.filename or "room.jpg")
    return result


@app.post("/api/design/generate")
async def design_generate(
    file: UploadFile = File(...),
    style: str = Form("modern"),
    palette: str = Form("neutral"),
    materials: str = Form(""),
    custom_desc: str = Form(""),
    strength: float = Form(0.65),
):
    """Generate redesigned room image."""
    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(400, "圖片太大，請上傳 20 MB 以下的圖片")
    if not (0.2 <= strength <= 0.95):
        raise HTTPException(400, "strength 須介於 0.2 – 0.95")

    materials_list = [m.strip() for m in materials.split(",") if m.strip()]
    room_stub = {"room_type": "interior room", "natural_light": "moderate"}
    positive, negative = build_prompt(room_stub, style, palette, materials_list, custom_desc)

    result = await generate_image(image_bytes, positive, negative, strength)
    if result is None:
        raise HTTPException(
            503,
            "圖片生成服務暫不可用。請在 .env 中設定 STABILITY_API_KEY 或 REPLICATE_API_TOKEN",
        )

    return StreamingResponse(
        io.BytesIO(result),
        media_type="image/jpeg",
        headers={"Content-Disposition": 'attachment; filename="design_result.jpg"'},
    )


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
