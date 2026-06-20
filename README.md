# 驗屋糾紛 AI 法律幫手

一個專門協助使用者理解「驗屋／房屋交易糾紛」相關法律問題的網頁應用：

- 法源：定期從法務部「全國法規資料庫」官方開放資料 API 下載法規全文（不是亂爬網頁，是官方提供的開放資料介面）
- AI：用 Claude API 做 RAG（檢索增強生成）——先從本地法條向量資料庫找出相關條文，再請 Claude 根據條文回答，並標明引用了哪一條
- 前端：簡單的網頁聊天介面

## 架構

```
backend/
  app/
    config.py        # 設定（法規白名單、API金鑰等）
    law_updater.py   # 從官方 API 下載並更新法規
    rag.py            # 把條文切塊、embedding、存進本地向量資料庫(Chroma)、檢索
    build_index.py    # CLI：重建索引
    chat.py            # 呼叫 Claude，產生附法源依據的回答
    main.py            # FastAPI 後端（/api/chat、/api/admin/update-laws）
  data/
    laws/              # 自動下載的法規 JSON（執行後才會產生）
    manual_docs/        # 手動補充的文件（如預售屋定型化契約應記載事項，官方API沒有提供）
    chroma/              # 向量資料庫檔案
frontend/
  index.html           # 聊天介面
```

## Step 1：取得 Claude API Key

去 https://console.anthropic.com/ 註冊並建立一支 API Key。

## Step 2：安裝環境

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 3：設定環境變數

```bash
cp .env.example .env
# 編輯 .env，填入你的 ANTHROPIC_API_KEY 和自訂的 ADMIN_TOKEN
```

## Step 4：下載法規 + 建立向量索引

```bash
# 從全國法規資料庫官方 API 下載 app/config.py 裡白名單列出的法規
python -m app.law_updater

# 把下載的法條切塊、embedding，建立本地向量索引
python -m app.build_index
```

> 第一次執行 `law_updater` 時，請檢查印出來的摘要：
> - `missing_in_source`：白名單裡的法規名稱在官方資料裡找不到對應項目（可能名稱打錯或法規已改名）
> - `no_articles_parsed`：抓到法規但條文解析失敗（官方 JSON 欄位名稱可能有變動，需要打開 `app/law_updater.py` 的 `_extract_articles()` 調整欄位對應）
>
> 法務部官方 API 不包含「預售屋/成屋買賣定型化契約應記載及不得記載事項」這類內政部公告。
> 這些文件放在 `glrs.moi.gov.tw`（內政部主管法規共用系統），會擋掉雲端環境常見的爬蟲 UA，
> 所以請在你自己的電腦/伺服器（一般網路即可）執行：
>
> ```bash
> python -m app.fetch_manual_docs
> ```
>
> 抓完務必打開 `backend/data/manual_docs/*.json` 核對內容是否為最新版本（網站改版可能讓自動分條失敗，
> 腳本會印出警告提示需要人工檢查），再重跑 `python -m app.build_index`。

## Step 5：本機測試

```bash
uvicorn app.main:app --reload --port 8000
```

打開瀏覽器到 http://localhost:8000 即可看到聊天介面（FastAPI 會直接把 `frontend/` 當靜態網站服務）。

## Step 8：法規自動更新

`app/main.py` 內已經用 APScheduler 排程「每週日凌晨 3 點」自動重新下載法規並重建索引。
若想手動立即更新，呼叫：

```bash
curl -X POST http://localhost:8000/api/admin/update-laws \
  -H "X-Admin-Token: 你在 .env 設定的 ADMIN_TOKEN"
```

## Step 6：讓手機 + 任何電腦都能使用（雲端部署）

### 方式 A：Railway（最簡單，有免費額度）

1. 去 https://railway.app 用 GitHub 帳號登入
2. New Project → Deploy from GitHub repo → 選這個 repo
3. 在 Railway 的 Variables 頁面加入環境變數：
   - `ANTHROPIC_API_KEY` = 你的 API Key
   - `ADMIN_TOKEN` = 自訂的管理密碼
4. 部署完成後 Railway 會自動給一個 `https://xxx.railway.app` 的網址
5. 用手機、電腦打開這個網址就能使用

> Railway 的免費方案每個月有 $5 美元額度，低流量個人使用通常夠用。

### 方式 B：Docker（自己的 VPS/NAS）

```bash
# 在你的伺服器上
git clone <this repo>
cd <repo>
cp backend/.env.example backend/.env
# 編輯 backend/.env 填入 ANTHROPIC_API_KEY 和 ADMIN_TOKEN

docker compose up -d

# 首次啟動後，還要下載法規並建立索引
docker compose exec app python -m app.law_updater
docker compose exec app python -m app.build_index
# 如果要抓定型化契約文件（需在有網路的環境執行）
docker compose exec app python -m app.fetch_manual_docs
```

伺服器 IP + 8000 port 就能從外部連線，建議前面再加 Nginx + Let's Encrypt 憑證（HTTPS）。

### 方式 C：本機開發（同一 WiFi 下手機也能連）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

手機和電腦在同一個 WiFi，手機用瀏覽器打開 `http://<電腦的區域網路IP>:8000` 即可。

---

## Step 7：法規自動更新

## 重要提醒

這個系統提供的是「一般法律資訊」，不是正式法律意見。所有回答都會在結尾提醒使用者：
具體案件請洽律師或地方政府消費者保護官／不動產糾紛調處委員會。
法規白名單、Prompt、引用機制都可以再依實際使用情況調整精修。
