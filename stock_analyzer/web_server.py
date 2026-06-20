"""
生技股分析網頁伺服器 - 行動裝置友善儀表板
使用方式：
  pip install fastapi uvicorn
  python web_server.py          # 電腦本機 http://localhost:8000
  python web_server.py --mobile # 手機可連（同一 WiFi）http://電腦IP:8000
  python web_server.py --port 8080  # 指定埠號
"""

import sys
import os
import time
import secrets
import argparse
from datetime import datetime
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, HTTPException, Request, Response, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from starlette.middleware.base import BaseHTTPMiddleware
    import uvicorn
except ImportError:
    print('⚠️  缺少套件，請先執行：')
    print('    pip install fastapi uvicorn python-multipart')
    sys.exit(1)

from config import STOCKS, PIPELINE
from catalyst import get_upcoming_catalysts, MAJOR_CONFERENCES_2026
from valuation import (calc_biotech_valuation, calc_product_npv,
                        calc_milestone_scenarios, calc_biotech_valuation_live)

app = FastAPI(title='台灣生技股儀表板')

# ── 簡易快取（30分鐘 TTL）──────────────────────────────────────
_cache: dict[str, tuple] = {}
CACHE_TTL = 1800  # 秒


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


# ── 登入驗證 ────────────────────────────────────────────────────
WEB_USERNAME = 'admin'        # 修改帳號
WEB_PASSWORD = 'biotech2026'  # 修改密碼

import hashlib as _hashlib

def _sign_token(token: str) -> str:
    """用固定密鑰簽署 token，讓 session 在 server 重啟後仍有效"""
    secret = f"{WEB_USERNAME}:{WEB_PASSWORD}:biotech_salt_2026"
    return _hashlib.sha256(f"{secret}:{token}".encode()).hexdigest()[:16]

def _valid_token(token: str) -> bool:
    """驗證 token 格式：<random>.<signature>"""
    if not token or '.' not in token:
        return False
    parts = token.rsplit('.', 1)
    if len(parts) != 2:
        return False
    rand, sig = parts
    return _sign_token(rand) == sig

_sessions: set = set()


class _AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ('/login', '/logout', '/api/health', '/js/app.js'):
            return await call_next(request)
        token = request.cookies.get('session')
        if not (token in _sessions or _valid_token(token or '')):
            if path.startswith('/api/'):
                return JSONResponse({'error': '請先登入', 'redirect': '/login'}, status_code=401)
            return RedirectResponse('/login', status_code=302)
        return await call_next(request)


app.add_middleware(_AuthMiddleware)


def _market_label(m: str) -> str:
    return {'twse': '上市', 'otc': '上櫃', 'innovation': '創新板',
            'emerging': '興櫃'}.get(m, m)


# ── 登入頁面 HTML ───────────────────────────────────────────────
_LOGIN_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>登入 - 台灣生技股儀表板</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"微軟正黑體","Noto Sans TC",sans-serif;
     background:linear-gradient(135deg,#1a237e,#3949ab);min-height:100vh;
     display:flex;align-items:center;justify-content:center;}
.box{background:#fff;border-radius:16px;padding:36px 32px;width:320px;
     box-shadow:0 8px 32px rgba(0,0,0,.3);}
.logo{text-align:center;font-size:22px;font-weight:700;color:#1a237e;margin-bottom:4px;}
.sub{text-align:center;font-size:12px;color:#888;margin-bottom:28px;}
input{display:block;width:100%;padding:12px 14px;border:2px solid #e0e0e0;
      border-radius:8px;font-size:15px;margin-bottom:14px;outline:none;
      transition:border-color .15s;font-family:inherit;}
input:focus{border-color:#1a237e;}
button{width:100%;padding:13px;background:#1a237e;color:#fff;border:none;
       border-radius:8px;font-size:16px;font-weight:700;cursor:pointer;letter-spacing:3px;}
button:active{background:#0d1b6e;}
.errmsg{display:none;background:#ffebee;border:1px solid #ef9a9a;border-radius:6px;
        padding:9px 12px;font-size:13px;color:#c62828;margin-bottom:14px;text-align:center;}
</style>
</head>
<body>
<div class="box">
  <div class="logo">🔬 台灣生技股儀表板</div>
  <div class="sub">請登入以繼續使用</div>
  <div class="errmsg" id="errmsg">❌ 帳號或密碼錯誤，請重試</div>
  <form method="post" action="/login">
    <input type="text" name="username" placeholder="帳號" autocomplete="username" autofocus>
    <input type="password" name="password" placeholder="密碼" autocomplete="current-password">
    <button type="submit">登 入</button>
  </form>
</div>
</body>
</html>'''


# ── API 端點 ────────────────────────────────────────────────

@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get('session') in _sessions:
        return RedirectResponse('/', status_code=302)
    return HTMLResponse(content=_LOGIN_HTML)


@app.post('/login')
async def login_post(username: str = Form(...), password: str = Form(...)):
    if username.strip() == WEB_USERNAME and password == WEB_PASSWORD:
        rand = secrets.token_urlsafe(24)
        token = f"{rand}.{_sign_token(rand)}"
        _sessions.add(token)
        r = RedirectResponse(url='/', status_code=303)
        r.set_cookie('session', token, httponly=True, samesite='lax', max_age=86400 * 30)
        return r
    return HTMLResponse(content=_LOGIN_HTML.replace(
        'id="errmsg"', 'id="errmsg" style="display:block"'), status_code=401)


@app.get('/logout')
async def logout(request: Request):
    token = request.cookies.get('session')
    if token:
        _sessions.discard(token)
    r = RedirectResponse(url='/login', status_code=303)
    r.delete_cookie('session')
    return r


@app.get('/', response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_HTML)


@app.get('/api/health')
async def api_health():
    return {'ok': True, 'time': datetime.now().isoformat()}


@app.get('/api/stocks')
async def api_stocks():
    return [
        {
            'code': code,
            'name': info['name'],
            'market': info['market'],
            'type': info['type'],
            'market_label': _market_label(info['market']),
            'products_count': len(PIPELINE.get(code, {}).get('products', [])),
        }
        for code, info in STOCKS.items()
    ]


@app.get('/api/catalyst')
async def api_catalyst():
    cached = _cache_get('catalyst')
    if cached:
        return cached

    all_events = []
    for code, info in STOCKS.items():
        for ev in get_upcoming_catalysts(code, days_ahead=730):
            all_events.append({
                'code': code,
                'name': info['name'],
                'date': ev.get('date', ''),
                'description': ev.get('description', ''),
                'event_type': ev.get('event_type', ''),
                'product': ev.get('product', ''),
                'impact': ev.get('impact', 'medium'),
                'direction': ev.get('direction', 'binary'),
                'notes': ev.get('notes', ''),
                'days_left': ev.get('days_left'),
            })

    conferences = [
        {'name': c['name'], 'full': c['full'],
         'period': c['period'], 'focus': c['focus']}
        for c in MAJOR_CONFERENCES_2026
    ]

    result = {
        'events': all_events,
        'conferences': conferences,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    _cache_set('catalyst', result)
    return result


@app.get('/api/stock/{code}')
async def api_stock(code: str):
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')

    cached = _cache_get(f'stock_{code}')
    if cached:
        return cached

    name = STOCKS[code]['name']
    stock_type = STOCKS[code]['type']

    try:
        from fetcher import get_price, get_price_history
        from chip import full_chip_report
        from alerts import check_price_alerts, check_chip_alerts, check_valuation_alerts

        price = get_price(code)
        price_hist = get_price_history(code, 20)
        chip = full_chip_report(code, name)

        val = None
        val_alerts = []
        if stock_type == 'biotech':
            share_price = price.get('close', 0) if price else 0
            val = calc_biotech_valuation(code, name, share_price=share_price)
            val_alerts = check_valuation_alerts(code, name, val)

        all_alerts = (check_price_alerts(code, name, price_hist)
                      + check_chip_alerts(chip)
                      + val_alerts)

        result = {
            'code': code, 'name': name, 'type': stock_type,
            'price': price, 'chip': chip,
            'valuation': val, 'alerts': all_alerts,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        _cache_set(f'stock_{code}', result)
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={
            'error': str(e), 'code': code, 'name': name,
            'hint': '確認電腦有連上台灣網路，且今天是交易日（週一~週五）',
        })


@app.get('/api/pipeline/{code}')
async def api_pipeline(code: str):
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')
    prods = PIPELINE.get(code, {}).get('products', [])
    return {
        'code': code,
        'name': STOCKS[code]['name'],
        'type': STOCKS[code]['type'],
        'products': [calc_product_npv(p) for p in prods],
    }


@app.get('/api/milestones/{code}')
async def api_milestones(code: str, price: float = 0.0):
    """里程碑市值推估（純本地計算，不需網路）"""
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')
    return calc_milestone_scenarios(code, STOCKS[code]['name'], share_price=price)


@app.get('/api/search/{code}')
async def api_search(code: str):
    """
    搜尋任意台股（不限於4支監控清單）
    回傳：股價、三大法人、融資融券、示警
    若為監控清單內生技股，額外回傳：估值 + 里程碑市值
    """
    code = code.strip().upper()
    cached = _cache_get(f'search_{code}')
    if cached:
        return cached

    in_watch = code in STOCKS
    name = STOCKS.get(code, {}).get('name', f'股票 {code}')
    stock_type = STOCKS.get(code, {}).get('type', 'general')

    try:
        from fetcher import get_price, get_price_history
        from chip import full_chip_report
        from alerts import check_price_alerts, check_chip_alerts

        price = get_price(code)
        if not price:
            return JSONResponse(status_code=404, content={
                'error': f'找不到股票 {code} 的資料',
                'hint': '確認代號正確（4位數字）且今天是交易日（週一~週五）、電腦連上台灣網路',
                'code': code,
            })

        price_hist = get_price_history(code, 20)
        chip = full_chip_report(code, name)
        alerts = check_price_alerts(code, name, price_hist) + check_chip_alerts(chip)

        result: dict = {
            'code': code,
            'name': name,
            'in_watchlist': in_watch,
            'type': stock_type,
            'price': price,
            'chip': chip,
            'alerts': alerts,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

        # 監控清單內生技股 → 額外估值 + 里程碑
        if in_watch and stock_type == 'biotech':
            from alerts import check_valuation_alerts
            share_price = price.get('close', 0) if price else 0
            val = calc_biotech_valuation(code, name, share_price=share_price)
            val_alerts = check_valuation_alerts(code, name, val)
            result['valuation'] = val
            result['alerts'] += val_alerts
            result['milestones'] = calc_milestone_scenarios(code, name, share_price)

        _cache_set(f'search_{code}', result)
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={
            'error': str(e), 'code': code, 'name': name,
            'hint': '確認電腦已連上台灣網路，且今天是交易日（週一~週五）',
        })


@app.get('/api/news')
async def api_news():
    """
    取得所有最新新聞（國際生技/財經 + FDA核准 + 台灣重大訊息 + 解盲偵測）
    首次執行約 30~60 秒（網路抓取），之後 30 分鐘快取
    """
    cached = _cache_get('news')
    if cached:
        return cached
    try:
        from news_fetcher import get_full_news_update
        result = get_full_news_update()
        _cache_set('news', result)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})


@app.get('/api/trials/{code}')
async def api_trials(code: str):
    """從 ClinicalTrials.gov 查詢單一公司臨床試驗（即時查詢）"""
    cached = _cache_get(f'trials_{code}')
    if cached:
        return cached
    try:
        from news_fetcher import get_ct_trials
        name = STOCKS.get(code, {}).get('name', f'股票{code}')
        trials = get_ct_trials(company=name, max_results=10)
        result = {'code': code, 'name': name, 'trials': trials,
                  'updated': datetime.now().strftime('%Y-%m-%d %H:%M')}
        _cache_set(f'trials_{code}', result)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})


@app.get('/api/live-pipeline/{code}')
async def api_live_pipeline(code: str):
    """
    即時從 ClinicalTrials.gov 比對最新臨床進度 vs config.py
    若有進展，同時回傳「即時估值」與「config估值」兩個結果
    快取 4 小時（CT.gov 資料不會分鐘級更新）
    """
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')

    cached = _cache_get(f'live_pipeline_{code}')
    if cached:
        return cached

    name = STOCKS[code]['name']
    try:
        from news_fetcher import get_live_pipeline_status

        live = get_live_pipeline_status(code)
        overrides = live.get('overrides', {})

        # 基準估值（config.py 版本）
        base_val = calc_biotech_valuation(code, name)

        # 即時估值（若有進展才會不同）
        live_val = None
        if overrides:
            live_val = calc_biotech_valuation_live(code, name,
                                                    live_overrides=overrides)

        result = {
            'code':           code,
            'name':           name,
            'live_status':    live,
            'base_valuation': base_val,
            'live_valuation': live_val,
            'has_advance':    bool(overrides),
            'checked_at':     live.get('checked_at', ''),
        }

        # 即時資料快取 4 小時（CT.gov 不需要分鐘級刷新）
        _cache[f'live_pipeline_{code}'] = (result, time.time() - CACHE_TTL + 14400)
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={
            'error': str(e), 'code': code,
            'hint': 'ClinicalTrials.gov 查詢失敗，請確認已連上網路'
        })


# ── 網頁 HTML（行動裝置友善）──────────────────────────────────

_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>台灣生技股儀表板</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"微軟正黑體","Noto Sans TC",sans-serif;
     background:#f0f4f8;color:#222;font-size:15px;line-height:1.5;}
.hdr{background:linear-gradient(135deg,#1a237e,#3949ab);color:#fff;
     padding:14px 16px;text-align:center;}
.hdr h1{font-size:17px;font-weight:700;}
.hdr p{font-size:11px;opacity:.75;margin-top:3px;}
.sgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;
        padding:10px;background:#e8edf5;}
@media(min-width:600px){.sgrid{grid-template-columns:repeat(4,1fr);}}
.scard{background:#fff;border-radius:10px;padding:12px;
       box-shadow:0 1px 4px rgba(0,0,0,.1);cursor:pointer;
       border:2px solid transparent;transition:border-color .15s;user-select:none;}
.scard.sel{border-color:#1a237e;}
.scode{font-size:19px;font-weight:700;color:#1a237e;}
.sname{font-size:13px;color:#555;}
.badge{display:inline-block;padding:1px 7px;border-radius:12px;
       font-size:10px;font-weight:600;margin-top:3px;}
.bb{background:#e8f5e9;color:#2e7d32;}
.bg{background:#e3f2fd;color:#1565c0;}
.mlbl{font-size:10px;color:#999;margin-top:2px;}
.tabs{display:flex;background:#fff;border-bottom:2px solid #e0e0e0;
      overflow-x:auto;-webkit-overflow-scrolling:touch;}
.tab{padding:11px 14px;cursor:pointer;white-space:nowrap;color:#777;
     border-bottom:3px solid transparent;font-size:13px;}
.tab.on{color:#1a237e;border-bottom-color:#1a237e;font-weight:600;}
.wrap{padding:10px;max-width:900px;margin:0 auto;}
.card{background:#fff;border-radius:10px;padding:14px;margin-bottom:10px;
      box-shadow:0 1px 5px rgba(0,0,0,.08);}
.ct{font-size:15px;font-weight:700;color:#1a237e;margin-bottom:10px;}
.loading{text-align:center;padding:40px;color:#aaa;}
.sp{width:36px;height:36px;border:4px solid #ddd;border-top-color:#1a237e;
    border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px;}
@keyframes spin{to{transform:rotate(360deg);}}
.ad{background:#ffebee;border-left:4px solid #e53935;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.aw{background:#fff8e1;border-left:4px solid #fb8c00;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.ap{background:#e8f5e9;border-left:4px solid #43a047;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.alb{font-size:11px;color:#888;margin-bottom:2px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{background:#f5f5f5;padding:7px 6px;text-align:left;font-size:11px;color:#666;white-space:nowrap;}
td{padding:7px 6px;border-bottom:1px solid #f0f0f0;vertical-align:middle;}
.ci{background:#f8f4ff;border-left:4px solid #7c4dff;padding:11px 12px;
    border-radius:6px;margin-bottom:8px;}
.cm{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}
.ck{font-weight:700;font-size:13px;}
.ch{color:#d50000;font-size:12px;font-weight:600;}
.cn{color:#7c4dff;font-size:12px;}
.ce{font-size:14px;}
.cno{font-size:11px;color:#888;margin-top:4px;}
.pf{display:flex;align-items:center;flex-wrap:wrap;gap:2px;margin:6px 0;}
.ph{font-size:10px;padding:2px 6px;border-radius:8px;white-space:nowrap;}
.phd{background:#e8f5e9;color:#43a047;}
.phc{background:#1a237e;color:#fff;font-weight:700;}
.phf{background:#f0f0f0;color:#bbb;}
.pha{color:#ccc;font-size:10px;}
.npvt{font-weight:700;background:#f9f9f9;}
.pb{font-size:32px;font-weight:700;}
.up{color:#e53935;}.dn{color:#43a047;}.fl{color:#757575;}
.edu{background:#e3f2fd;border-radius:7px;padding:9px 11px;
     font-size:12px;color:#1565c0;margin-bottom:10px;}
.edu b{color:#0d47a1;}
.sg{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;}
.sc{background:#fafafa;border-radius:6px;padding:8px 10px;}
.sc .lb{font-size:11px;color:#888;}.sc .vl{font-size:15px;font-weight:700;}
.cof{display:flex;justify-content:space-between;align-items:center;
     padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px;}
.cnm{font-weight:600;}.cdt{font-size:11px;color:#888;}
.empty{text-align:center;padding:40px;color:#bbb;font-size:14px;}
</style>
</head>
<body>
<div class="hdr" style="position:relative">
  <a href="/logout" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);
     color:rgba(255,255,255,.75);font-size:12px;text-decoration:none;
     background:rgba(255,255,255,.15);padding:4px 12px;border-radius:12px;">登出</a>
  <h1>🔬 台灣生技股儀表板</h1>
  <p>漢康-KY(7827)&nbsp;·&nbsp;康霈(6919)&nbsp;·&nbsp;泰合(6467)&nbsp;·&nbsp;竟天(6917)</p>
</div>
<div id="sg" class="sgrid"></div>
<div class="tabs" id="tb">
  <div class="tab on"  data-t="cat"  onclick="sw(this)">📅 催化劑</div>
  <div class="tab"     data-t="chip" onclick="sw(this)">📊 籌碼</div>
  <div class="tab"     data-t="val"  onclick="sw(this)">💰 估值</div>
  <div class="tab"     data-t="ale"  onclick="sw(this)">⚡ 示警</div>
  <div class="tab"     data-t="pip"  onclick="sw(this)">🧬 管線</div>
  <div class="tab"     data-t="srch" onclick="sw(this)">🔍 查任何股</div>
  <div class="tab"     data-t="news" onclick="sw(this)">📰 新聞</div>
</div>
<div class="wrap" id="mc">
  <div class="loading"><div class="sp"></div><p>載入中...</p></div>
</div>
<noscript><div style="text-align:center;padding:40px;color:red">⚠️ 請啟用 JavaScript 才能使用本頁面</div></noscript>
<script src="/js/app.js"></script>
</body>
</html>'''

_JS_CODE = """
console.log('[biotech] JS loaded, checking DOM...');
(function(){
  var e=document.getElementById('mc');
  console.log('[biotech] mc element:', e ? 'FOUND id='+e.id : 'NULL - not found!');
  if(e)e.innerHTML='<div class="loading"><div class="sp"></div><p>連線中，首次載入約5~15秒...</p></div>';
  else document.body&&(document.body.style.background='red');
})();
console.log('[biotech] IIFE done');
var stocks=[],sel=null,tab="cat",cache={};
window.onerror=function(msg,src,ln){
  var e=document.getElementById('mc');
  if(e)e.innerHTML='<div class="card" style="color:#c62828;padding:16px">⚠️ JS錯誤：'+msg+' (行'+ln+')<br><button onclick="location.reload()" style="margin-top:8px;padding:6px 16px;background:#1a237e;color:#fff;border:none;border-radius:6px;cursor:pointer">重新整理</button></div>';
  return false;
};
window.onunhandledrejection=function(ev){
  var e=document.getElementById('mc');
  if(e)e.innerHTML='<div class="card" style="color:#c62828;padding:16px">⚠️ 非同步錯誤：'+(ev.reason&&ev.reason.message||ev.reason)+'<br><button onclick="init()" style="margin-top:8px;padding:6px 16px;background:#1a237e;color:#fff;border:none;border-radius:6px;cursor:pointer">重試</button></div>';
};
function $(i){return document.getElementById(i);}
function mc(h){var e=$("mc");if(e)e.innerHTML=h;}
async function init(){
  mc('<div class="loading"><div class="sp"></div><p>連線中，首次載入約5~15秒...</p></div>');
  try{
    stocks=await jget("/api/stocks");
    rg();rt();
  }catch(e){
    mc('<div class="card" style="color:#c62828;padding:16px">⚠️ 載入失敗：'+e.message+'<br><button onclick="init()" style="margin-top:8px;padding:6px 16px;background:#1a237e;color:#fff;border:none;border-radius:6px;cursor:pointer">重試</button></div>');
  }
}
function rg(){
  $("sg").innerHTML=stocks.map(function(s){
    return '<div class="scard'+(sel===s.code?" sel":"")
      +'" onclick="ss(\\\''+s.code+'\\\')">'
      +'<div class="scode">'+s.code+'</div>'
      +'<div class="sname">'+s.name+'</div>'
      +'<div><span class="badge '+(s.type==="biotech"?"bb":"bg")+'">'
      +(s.type==="biotech"?"🔬生技":"📈一般")+'</span></div>'
      +'<div class="mlbl">'+s.market_label+"&nbsp;·&nbsp;"+s.products_count+"項產品</div>"
      +"</div>";
  }).join("");
}
function ss(c){sel=(sel===c)?null:c;rg();rt();}
function sw(el){
  tab=el.getAttribute("data-t");
  document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("on");});
  el.classList.add("on");rt();
}
function rt(){
  ({cat:tCat,chip:tChip,val:tVal,ale:tAle,pip:tPip,srch:tSearch,news:tNews})[tab]();
}

/* ── 催化劑 ── */
async function tCat(){
  mc(ld("催化劑日曆"));
  try{
    var d=await jcached("/api/catalyst");
    var evs=d.events||[];
    if(sel)evs=evs.filter(function(e){return e.code===sel;});
    evs.sort(function(a,b){return(a.days_left===null?9999:a.days_left)-(b.days_left===null?9999:b.days_left);});
    var h=edu("催化劑是可能讓股價大漲或大跌的關鍵事件，例如：<b>臨床數據公布、FDA審查結果、授權合作宣布</b>。"
      +"<br>🔴高影響事件成功=可能漲30~100%，失敗=可能跌30~60%，要特別留意。");
    if(!evs.length){h+='<div class="empty">📭 無催化劑事件</div>';}
    else{
      h+=evs.map(function(e){
        var dc=e.direction==="positive"?"color:#2e7d32":e.direction==="negative"?"color:#c62828":"color:#e65100";
        var di=e.direction==="positive"?"📈":e.direction==="negative"?"📉":"⚡";
        var ii=e.impact==="high"?'<span style="color:#e53935">🔴高影響</span>'
                :e.impact==="medium"?'<span style="color:#fb8c00">🟡中影響</span>'
                :'<span style="color:#43a047">🟢低影響</span>';
        return '<div class="ci">'
          +'<div class="cm"><span class="ck">'+e.name+"("+e.code+")</span>"
          +'<span>'+dl(e.days_left,e.date)+"</span></div>"
          +'<div class="ce"><span style="'+dc+'">'+di+"</span> "+e.description+"</div>"
          +'<div style="font-size:11px;margin-top:3px;">'+ii+" · "+e.product+"</div>"
          +(e.notes?'<div class="cno">💬 '+e.notes+"</div>":"")
          +"</div>";
      }).join("");
    }
    h+='<div class="card"><div class="ct">🏥 重要國際醫學年會（2026）</div>'
      +edu("生技公司常在這些年會發表臨床數據。<b>公布前一週往往提前炒作，公布當天大幅波動</b>，小心追高。")
      +(d.conferences||[]).map(function(c){
          return '<div class="cof"><div><div class="cnm">'+c.name+" "+c.full+"</div>"
            +'<div style="font-size:11px;color:#7c4dff">焦點：'+c.focus+"</div></div>"
            +'<div class="cdt">'+c.period+"</div></div>";
        }).join("")+"</div>";
    mc(h);
  }catch(e){mc(err(e.message));}
}

/* ── 籌碼 ── */
async function tChip(){
  if(!sel){mc(nos());return;}
  mc(ld("籌碼資料（首次約10~30秒）"));
  try{
    var d=await jcached("/api/stock/"+sel);
    if(d.error){mc(nerr(d.error,d.hint));return;}
    var chip=d.chip||{},inst=chip.institutional||{},marg=chip.margin||{};
    var h=edu("<b>三大法人</b>是市場主力：外資（外國大機構）、投信（台灣基金）、自營商（券商自己錢）。"
      +"<br>他們連續買進=強力看多；突然大量賣出=要警戒。"
      +"<br><b>融資</b>=借錢買股（槓桿），融資增+股價跌=最危險組合。<b>融券</b>=借股放空。");
    if(!inst.error){
      h+='<div class="card"><div class="ct">🏦 三大法人 <span style="font-size:12px;font-weight:400;color:#888">近'+(inst.days_analyzed||"?")+"個交易日</span></div>"
        +"<table><tr><th>法人</th><th>今日淨買賣(張)</th><th>方向</th><th>連續</th><th>累計(張)</th></tr>"
        +["foreign","trust","dealer","total"].map(function(k){
          var lb={foreign:"外資",trust:"投信",dealer:"自營",total:"合計"}[k];
          var di=inst[k]||{},net=di.latest_net||0,cum=di.cumsum||0;
          return'<tr'+(k==="total"?' style="font-weight:700;background:#fafafa"':"")+">"
            +"<td>"+lb+"</td>"
            +'<td class="'+(net>0?"up":net<0?"dn":"fl")+'">'+fs(net)+"</td>"
            +"<td>"+(di.direction==="買超"?"📈 買":"📉 賣")+"</td>"
            +"<td>"+(di.consecutive||0)+"天</td>"
            +'<td class="'+(cum>0?"up":cum<0?"dn":"")+'">'+fs(cum)+"</td>"
            +"</tr>";
        }).join("")+"</table>"
        +(inst.signals||[]).map(function(s){return'<div style="margin-top:6px;font-size:13px">'+s+"</div>";}).join("")
        +edu("📖 <b>外資+投信同向買超3天以上</b>→強看多信號。外資是最大主力，動向最重要。")
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 三大法人資料無法取得（非交易日或網路問題）</p></div>';
    }
    if(!marg.error){
      var m=marg.margin||{},sh=marg.short||{};
      h+='<div class="card"><div class="ct">💳 融資融券 <span style="font-size:12px;font-weight:400;color:#888">'+(marg.latest_date||"")+"</span></div>"
        +"<table><tr><th>項目</th><th>數值</th><th>說明</th></tr>"
        +"<tr><td>融資餘額</td><td>"+fn(m.balance)+" 張</td><td>借錢買股的人持有量</td></tr>"
        +'<tr><td>今日增減</td><td class="'+(m.change>0?"up":m.change<0?"dn":"")+'">'+fs(m.change)+" 張</td><td>正數=槓桿增加</td></tr>"
        +"<tr><td>5日趨勢</td><td>"+fs(m.trend_5d)+" 張</td><td>"+(m.trend_5d_label||"")+"</td></tr>"
        +"<tr><td>融資使用率</td><td>"+fp(marg.margin_usage_pct)+"</td><td>使用率越高越危險</td></tr>"
        +"<tr><td>融券餘額</td><td>"+fn(sh.balance)+" 張</td><td>放空者持有量</td></tr>"
        +"<tr><td>券資比</td><td>"+((sh.ratio_pct||0).toFixed(1))+"%</td><td>&lt;15%正常，&gt;25%空頭強勢</td></tr>"
        +"</table>"
        +(marg.signals||[]).map(function(s){return'<div style="margin-top:6px;font-size:13px">'+s+"</div>";}).join("")
        +edu("📖 <b>最危險組合</b>：融資增加＋股價下跌。代表散戶用借來的錢攤平，可能引發斷頭連鎖賣壓。")
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 融資融券資料無法取得</p></div>';
    }
    mc(h);
  }catch(e){mc(err(e.message));}
}

/* ── 估值 ── */
async function tVal(){
  if(!sel){mc(nos());return;}
  mc(ld("估值計算"));
  try{
    var d=await jcached("/api/stock/"+sel);
    if(d.error){mc(nerr(d.error,d.hint));return;}
    var val=d.valuation,price=d.price;
    var curPrice=price?(price.close||0):0;
    var h=edu("<b>生技股估值 vs 一般股票估值的差別</b>"
      +"<br>一般股票用「本益比(P/E)=股價÷每股獲利」，但生技股<b>還沒賺錢</b>，無法計算。"
      +"<br>生技股改用 <b>rNPV法</b>：未來可能賺多少 × 成功機率 × 時間折現 = 理論價值。"
      +"<br>市場通常給予 rNPV 2~8倍的「溢價」（期待值），Phase越早倍數越高。"
      +"<br>⚠️ 市場情緒可能遠高或遠低於計算值，這是工具，不是保證。");
    if(price){
      var chg=price.change||0,cls=chg>0?"up":chg<0?"dn":"fl";
      h+='<div class="card"><div class="ct">📈 最新股價</div>'
        +'<div class="pb '+cls+'">'+(price.close||"N/A")+'</div>'
        +'<div style="margin-top:4px;font-size:14px" class="'+cls+'">'
        +(chg>0?"▲ +":chg<0?"▼ ":"─ ")+Math.abs(chg).toFixed(2)+" 元</div>"
        +'<div class="sg">'
        +sc("開盤",price.open)+sc("最高",price.high)
        +sc("最低",price.low)+sc("成交量",fn(Math.round((price.volume||0)/1000))+"張")
        +"</div>"
        +'<div style="font-size:11px;color:#888;margin-top:6px">資料日期：'+(price.date||"")+" · 來源："+(price.source||"")+"</div>"
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 股價資料無法取得（非交易日）</p></div>';
    }
    if(val&&!val.status){
      var prods=val.pipeline_products||[];
      h+='<div class="card"><div class="ct">💊 Pipeline rNPV 估值明細</div>'
        +"<table><tr><th>產品</th><th>階段</th><th>最終成功率</th><th>rNPV(億台幣)</th></tr>"
        +prods.map(function(p){
          return"<tr><td style='font-size:11px'>"+p.name+"</td>"
            +"<td>"+pb(p.phase)+"</td>"
            +"<td>"+(p.prob_success*100).toFixed(0)+"%</td>"
            +"<td style='font-weight:600'>"+(p.rnpv_twd_mn/100).toFixed(1)+"</td></tr>";
        }).join("")
        +'<tr class="npvt"><td colspan="3">Pipeline 合計</td>'
        +"<td>"+((val.total_pipeline_twd_mn||0)/100).toFixed(1)+" 億台幣</td></tr>"
        +"</table>"
        +edu("📖 <b>成功率</b>是「從現在這個Phase到最終上市並產生收益的歷史機率」，不是本步驟成功率。<br>"
          +"rNPV = 峰值銷售 × 授權金率 × 4倍收益乘數 × 成功率 ÷ 折現")
        +"</div>";
      if(val.cash_runway_months){
        var rw=val.cash_runway_months,ri=rw<12?"🔴":rw<18?"⚠️":"✅";
        h+='<div class="card">'+ri+" <b>現金跑道："+rw.toFixed(1)+" 個月</b>"
          +'<div style="font-size:12px;color:#888;margin-top:4px">現金不夠就要再募資（稀釋股本），跑道越短風險越高。</div>'
          +"</div>";
      }else{
        h+='<div class="card" style="font-size:13px;color:#999">ℹ️ 現金跑道需更新財報資料（config.py填入cash_twd_mn + burn_rate_twd_mn）。建議每季查看！</div>';
      }
    }else if(val&&val.status){
      h+='<div class="card"><p>⚠️ '+val.status+"</p></div>";
    }
    // ── 即時臨床進度比對（CT.gov vs config）────────────────────
    h+='<div id="live_status_area"><div class="edu" style="font-size:12px">⏳ 正在向 ClinicalTrials.gov 查詢最新臨床進度...</div></div>';
    mc(h);
    // 非同步載入即時進度（不阻塞主要估值顯示）
    jget("/api/live-pipeline/"+sel).then(function(lv){
      var la=document.getElementById("live_status_area");
      if(!la)return;
      var lh=rLiveStatus(lv);
      la.innerHTML=lh;
    }).catch(function(){
      var la=document.getElementById("live_status_area");
      if(la)la.innerHTML='<div class="edu" style="font-size:11px;color:#bbb">⚠️ CT.gov 查詢逾時（非交易時段或網路較慢，不影響本頁估值）</div>';
    });
    // 里程碑市值對照表（本地計算）
    try{
      var ms=await jget("/api/milestones/"+sel+(curPrice?"?price="+curPrice:""));
      var msel=document.getElementById("live_status_area");
      if(msel)msel.insertAdjacentHTML("afterend",rMilestone(ms));
    }catch(ex){}
  }catch(e){mc(err(e.message));}
}

/* ── CT.gov 即時進度比對渲染 ── */
function rLiveStatus(lv){
  if(!lv||lv.error)return'<div class="edu" style="font-size:11px;color:#bbb">⚠️ CT.gov 即時查詢無結果：'+(lv&&lv.error||"逾時")+"</div>";
  var updates=lv.live_status&&lv.live_status.updates||[];
  var overrides=lv.live_status&&lv.live_status.overrides||{};
  var hasAdv=lv.has_advance;
  var checked=lv.checked_at||lv.live_status&&lv.live_status.checked_at||"";

  // ── 進度比對結果 ──
  var h='<div class="card"><div class="ct">📡 ClinicalTrials.gov 即時進度核對 <span style="font-size:11px;font-weight:400;color:#888">'+checked+"</span></div>"
    +edu(hasAdv
      ?"🚨 <b>偵測到進度更新！</b> CT.gov 顯示的臨床進度比 config.py 更新，下方「即時估值」已自動用最新 Phase 重算，請確認後更新 config.py。"
      :"✅ CT.gov 資料與 config.py 一致（或未能匹配到試驗），估值使用 config 資料。<br>若公司最近有重大進展，建議更新 config.py。");

  if(updates.length){
    h+="<table><tr><th>產品</th><th>config 階段</th><th>CT.gov 階段</th><th>試驗狀態</th><th>最後更新</th><th>查看</th></tr>"
      +updates.map(function(u){
        var adv=u.is_advanced;
        var comp=u.is_completed&&!adv;
        var row_style=adv?'style="background:#fff8e1"':comp?'style="background:#e3f2fd"':"";
        return'<tr '+row_style+'>'
          +'<td style="font-size:11px">'+u.product+"</td>"
          +'<td>'+pb(u.config_phase)+"</td>"
          +'<td>'+(adv?'<span style="background:#ffecb3;color:#e65100;padding:2px 6px;border-radius:6px;font-size:11px;font-weight:700">⬆ '+u.live_phase+"</span>":pb(u.live_phase||u.config_phase))+"</td>"
          +'<td style="font-size:11px;color:#888">'+_ctStatus(u.ct_status)+"</td>"
          +'<td style="font-size:10px;color:#aaa">'+(u.last_update||"—")+"</td>"
          +'<td>'+(u.nct_id?'<a href="'+(u.ct_url||"#")+'" target="_blank" style="font-size:11px;color:#1565c0">'+u.nct_id+"</a>":"—")+"</td>"
          +"</tr>";
      }).join("")+"</table>";
  }else{
    h+='<div style="color:#bbb;font-size:13px;padding:8px">CT.gov 未查詢到匹配的試驗（可能因公司規模小，試驗未登錄到 CT.gov，或藥物代號不符）</div>';
  }
  h+="</div>";

  // ── 即時估值 vs config 估值對照 ──
  if(hasAdv&&lv.live_valuation){
    var bv=lv.base_valuation,lval=lv.live_valuation;
    var bTotal=(bv.total_pipeline_twd_mn||0)/100;
    var lTotal=(lval.total_pipeline_twd_mn_live||0)/100;
    var uplift=((lval.live_uplift_twd_mn||0)/100).toFixed(1);
    // 計算合理股價（NAV per share）
    var bNav=bv.nav_per_share_twd;
    var bTotalVal=bv.total_value_twd_mn||0;
    var liveCash=bv.cash_twd_mn||0;
    var liveNavPS=null;
    if(bNav&&bNav>0&&bTotalVal>0){
      var sharesMn=bTotalVal/bNav;
      var lTotalVal=(lTotal*100)+liveCash;
      liveNavPS=Math.round(lTotalVal/sharesMn*10)/10;
    }
    h+='<div class="card" style="border:2px solid #fb8c00"><div class="ct">🔄 即時估值 vs config 估值對照</div>'
      +edu("CT.gov 顯示有進展，<b>下方即時估值已自動用最新 Phase 重算</b>。"
        +"若確認公告屬實，請更新 config.py 的 phase 欄位，使兩者一致。");
    h+='<div class="sg">'
      +sc("config 估值(億台幣)",bTotal.toFixed(1))
      +sc("即時估值(億台幣)",'<span style="color:#e65100;font-weight:700">'+lTotal.toFixed(1)+"</span>")
      +sc("即時估值增加",uplift>=0?'<span style="color:#e65100">+'+uplift+"億</span>":'<span style="color:#2e7d32">'+uplift+"億</span>")
      +sc("更新項目",Object.keys(overrides).length+"個產品")
      +(bNav?sc("config 合理股價(元)",bNav.toFixed(1)):"")
      +(liveNavPS?sc("即時合理股價(元)",'<span style="color:#e65100;font-weight:700">'+liveNavPS.toFixed(1)+"</span>"):"")
      +"</div>"
      +'<div style="font-size:12px;color:#888;margin-top:8px">📝 <b>更新 config.py 方法</b>：'
      +"找到對應產品的 'phase' 欄位，改成 CT.gov 顯示的新 Phase，儲存後重啟伺服器即生效。"
      +"</div></div>";
    // 即時產品 NPV 明細
    var liveProd=lval.pipeline_products_live||[];
    if(liveProd.length){
      h+='<div class="card"><div class="ct">💊 即時 Pipeline rNPV（用最新 Phase 重算）</div>'
        +"<table><tr><th>產品</th><th>階段</th><th>成功率</th><th>rNPV(億台幣)</th><th>說明</th></tr>"
        +liveProd.map(function(p){
          var upd=p._live_updated;
          return"<tr"+(upd?' style="background:#fff8e1"':"")+">"
            +"<td style='font-size:11px'>"+p.name+"</td>"
            +"<td>"+pb(p.phase)+(upd?'<span style="font-size:9px;color:#e65100;margin-left:3px">↑CT.gov</span>':"")+"</td>"
            +"<td>"+(p.prob_success*100).toFixed(0)+"%</td>"
            +"<td style='font-weight:600'>"+(p.rnpv_twd_mn/100).toFixed(1)+"</td>"
            +"<td style='font-size:10px;color:#888'>"+(upd?"原"+p._original_phase+"→"+p.phase:"config資料")+"</td>"
            +"</tr>";
        }).join("")+"</table></div>";
    }
  }
  return h;
}
function _ctStatus(s){
  var m={
    'RECRUITING':'🟢 收案中','ACTIVE_NOT_RECRUITING':'🔵 收案完成/試驗進行中',
    'COMPLETED':'✅ 已完成','NOT_YET_RECRUITING':'⏳ 尚未開始收案',
    'TERMINATED':'🔴 已終止','WITHDRAWN':'⚫ 已撤回','ENROLLING_BY_INVITATION':'🟡 邀請收案',
  };
  return m[s]||s||'—';
}

/* ── 里程碑市值對照表渲染 ── */
function rMilestone(ms){
  if(ms.error)return'<div class="card" style="color:#999">ℹ️ 里程碑資料：'+ms.error+"</div>";
  var h='<div class="card"><div class="ct">📊 里程碑達標市值對照表</div>'
    +edu("<b>怎麼使用這張表？</b><br>"
      +"• <b>現況合理市值</b>：rNPV × 市場溢價倍數（"+ms.base_premium[0]+"~"+ms.base_premium[1]+"x），"
        +"代表「現在這個進度下市場應給的理論市值」<br>"
      +"• <b>每一情境</b>：若該里程碑達標，rNPV重新計算（成功率↑、距上市年數↓），市值重評<br>"
      +"• <b>本步成功率</b>：這個Phase轉換的歷史平均機率（Phase2→3只有37%，最難）<br>"
      +"• <b>增幅</b>：達標後合理市值比現況增加多少億（因溢價倍數同步調整，可能不如直覺大）<br>"
      +"💡 看法：增幅大＋本步成功率高 = 最優質催化劑");
  // 現況列
  h+="<div style='overflow-x:auto'><table style='font-size:12px;min-width:500px'>"
    +"<tr><th>情境</th><th style='max-width:130px'>產品</th><th>合計rNPV</th><th>合理市值區間<br>(億台幣)</th><th>本步<br>成功率</th><th>較現況<br>增幅(億)</th></tr>"
    +"<tr style='background:#e3f2fd;font-weight:700'>"
    +"<td>📍 現況</td><td>—</td>"
    +"<td>"+ms.current_rnpv_bn+"億</td>"
    +"<td style='color:#1565c0'>"+ms.base_mkt_cap_low_bn+"~"+ms.base_mkt_cap_high_bn+"</td>"
    +"<td>—</td><td style='color:#888'>基準</td></tr>";
  var phase_icons={"Phase1":"🧪","Phase2":"🔬","Phase3":"🏥","NDA/BLA":"📋","Approved":"✅"};
  (ms.scenarios||[]).forEach(function(s){
    var icon=phase_icons[s.to_phase]||"🎯";
    var upOk=s.uplift_low_bn>0||s.uplift_high_bn>0;
    var upStr=(s.uplift_low_bn>=0?"+":"")+s.uplift_low_bn+"~"+(s.uplift_high_bn>=0?"+":"")+s.uplift_high_bn;
    var pname=s.product.length>16?s.product.slice(0,16)+"…":s.product;
    h+="<tr>"
      +"<td>"+icon+" "+s.from_phase+"<br>→"+s.to_phase+"</td>"
      +"<td style='font-size:11px;color:#555'>"+pname+"</td>"
      +"<td>"+s.new_rnpv_bn+"億</td>"
      +"<td style='font-weight:700;color:#1a237e'>"+s.mkt_cap_low_bn+"~"+s.mkt_cap_high_bn+"</td>"
      +"<td style='color:#888'>"+s.step_prob_pct+"%</td>"
      +'<td class="'+(upOk?"up":"dn")+'">'+upStr+"</td>"
      +"</tr>";
  });
  h+="</table></div>";
  // 現在市值 vs 合理市值（若有股本）
  if(ms.curr_mkt_cap_bn){
    var pf=ms.premium_vs_fair,pfcls=pf>30?"up":pf<-30?"dn":"fl";
    h+='<div style="margin-top:10px;padding:10px;background:#fafafa;border-radius:6px;font-size:13px">'
      +"<b>現在市值："+ms.curr_mkt_cap_bn+"億</b>"
      +"  vs  合理市值 "+ms.base_mkt_cap_low_bn+"~"+ms.base_mkt_cap_high_bn+"億"
      +'<span class="'+pfcls+'" style="margin-left:8px">'+(pf>=0?"溢價 +":"折價 ")+Math.abs(pf)+"%</span>"
      +(ms.fair_price_low?'<div style="font-size:12px;color:#888;margin-top:3px">合理股價估算：'+ms.fair_price_low+"~"+ms.fair_price_high+" 元</div>":"")
      +"</div>";
  }else{
    h+='<div class="edu" style="margin-top:8px;font-size:11px">ℹ️ <b>想看「現在股價貴不貴」？</b>'
      +'填入 config.py 的 shares_mn（流通股數，百萬股）即可自動計算。'
      +'查詢來源：公開資訊觀測站(mops.twse.com.tw)→財務分析→每股參考資訊，或看季報封面「普通股股數」。'
      +"</div>";
  }
  h+='<div style="font-size:10px;color:#bbb;margin-top:8px">📌 '+ms.premium_note+"</div>"
    +"</div>";
  return h;
}

/* ── 示警 ── */
async function tAle(){
  mc(ld("示警掃描"));
  var codes=sel?[sel]:stocks.map(function(s){return s.code;});
  var all=[];
  for(var i=0;i<codes.length;i++){
    try{
      var d=await jcached("/api/stock/"+codes[i]);
      if(d.alerts)(d.alerts).forEach(function(a){all.push(Object.assign({},a,{code:codes[i],sn:d.name}));});
    }catch(e){}
  }
  var h=edu("<b>示警等級：</b>"
    +"<br>🔴 危險 = 需立即關注（融資斷頭風險、現金快耗盡等）"
    +"<br>⚠️ 注意 = 持續觀察，未來可能惡化"
    +"<br>✅ 正面 = 有利訊號（不保證上漲，仍需綜合判斷）");
  if(!all.length){
    h+='<div class="empty">✅ 目前無示警<br><span style="font-size:12px">（或資料無法取得，確認已連上台灣網路且是交易日）</span></div>';
  }else{
    var o={"🔴":0,"⚠️":1,"✅":2};
    all.sort(function(a,b){return(o[a.level]||9)-(o[b.level]||9);});
    h+=all.map(function(a){
      var c=a.level==="🔴"?"ad":a.level==="⚠️"?"aw":"ap";
      return'<div class="'+c+'"><div class="alb">'+a.sn+"("+a.code+")</div>"
        +a.level+" "+a.msg+"</div>";
    }).join("");
  }
  mc(h);
}

/* ── 研發管線 ── */
async function tPip(){
  mc(ld("研發管線"));
  var codes=sel?[sel]:stocks.map(function(s){return s.code;});
  var h=edu("<b>藥物研發各階段成功率（業界統計）：</b>"
    +"<br>Phase1(安全性)→52% | Phase2(初步療效)→28% | Phase3(大規模)→57% | NDA審查→85%"
    +"<br>累計從Phase1到上市的整體成功率約 <b>8~12%</b>（非常低）。"
    +"<br>📊 Phase3成功→股價通常翻倍；Phase3失敗→通常腰斬。");
  for(var i=0;i<codes.length;i++){
    try{
      var d=await jcached("/api/pipeline/"+codes[i]);
      h+='<div class="card"><div class="ct">🧬 '+d.name+"("+d.code+")</div>"
        +(d.products||[]).map(function(p){
          return'<div style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #f0f0f0">'
            +'<div style="font-weight:600;margin-bottom:2px">'+p.name+"</div>"
            +'<div style="font-size:12px;color:#666;margin-bottom:6px">'+p.indication+"｜"+p.territory+"</div>"
            +pf(p.phase)
            +'<div class="sg" style="margin-top:8px">'
            +sc("成功率",(p.prob_success*100).toFixed(0)+"%")
            +sc("距上市","約"+p.years_to_mkt+"年")
            +sc("峰值銷售","USD "+p.peak_sales_bn+"B")
            +sc("rNPV",(p.rnpv_twd_mn/100).toFixed(1)+"億台幣")
            +"</div></div>";
        }).join("")
        +(d.products.length===0?'<p style="color:#bbb;font-size:13px">尚無產品資料</p>':"")
        +"</div>";
    }catch(e){}
  }
  mc(h);
}

/* ── Helper ── */
function ld(w){return'<div class="loading"><div class="sp"></div><p>載入'+w+'...</p></div>';}
function nos(){return'<div class="empty">👆 請先點選上方股票<br><span style="font-size:12px;color:#bbb">再點一次可取消篩選，顯示全部</span></div>';}
function err(m){return'<div class="card"><p style="color:red">⚠️ 發生錯誤：'+m+"</p></div>";}
function nerr(m,h){return'<div class="card"><p style="color:#e53935">⚠️ '+m+"</p>"+(h?'<p style="margin-top:8px;font-size:13px;color:#888">💡 '+h+"</p>":"")+"</div>";}
function edu(t){return'<div class="edu">💡 '+t+"</div>";}
function sc(l,v){return'<div class="sc"><div class="lb">'+l+'</div><div class="vl">'+(v===null||v===undefined?"N/A":v)+"</div></div>";}
function fn(n){if(n===null||n===undefined)return"N/A";return Number(n).toLocaleString();}
function fs(n){if(n===null||n===undefined)return"N/A";return(n>=0?"+":"")+fn(n);}
function fp(n){if(n===null||n===undefined||n==="N/A")return"N/A";return parseFloat(n).toFixed(1)+"%";}
function dl(days,ds){
  if(days===null||days===undefined)return'<span class="cn">📅 '+ds+"</span>";
  if(days<0)return'<span class="cn">'+Math.abs(days)+"天前</span>";
  if(days===0)return'<span class="ch">【今日！】</span>';
  if(days<=7)return'<span class="ch">⚡ '+days+"天後</span>";
  if(days<=30)return'<span style="color:#e65100;font-size:12px">'+days+"天後</span>";
  return'<span class="cn">'+Math.ceil(days/30)+"個月後</span>";
}
function pb(ph){
  var c={"Pre-IND":"#90a4ae","Phase1":"#64b5f6","Phase2":"#4fc3f7",
          "Phase3":"#4db6ac","NDA/BLA":"#ff8a65","Approved":"#81c784"}[ph]||"#90a4ae";
  return'<span style="background:'+c+'22;color:'+c+';padding:2px 7px;border-radius:8px;font-size:11px;font-weight:600">'+ph+"</span>";
}
function pf(cur){
  var phs=["Pre-IND","Phase1","Phase2","Phase3","NDA/BLA","Approved"];
  var idx=phs.indexOf(cur);
  return'<div class="pf">'+phs.map(function(p,i){
    var c=i<idx?"phd":i===idx?"phc":"phf";
    return'<span class="ph '+c+'">'+p+"</span>"+(i<phs.length-1?'<span class="pha">›</span>':"");
  }).join("")+"</div>";
}
async function jcached(url){
  if(cache[url]&&cache[url].ts&&(Date.now()-cache[url].ts<1800000))return cache[url].data;
  var data=await jget(url);cache[url]={data:data,ts:Date.now()};return data;
}
async function jget(url){
  var ctrl=new AbortController();
  var tid=setTimeout(function(){ctrl.abort();},15000);
  try{
    var r=await fetch(url,{signal:ctrl.signal});
    clearTimeout(tid);
    if(r.status===401){window.location.href='/login';throw new Error('請重新登入');}
    if(!r.ok)throw new Error("HTTP "+r.status);
    return await r.json();
  }catch(ex){
    clearTimeout(tid);
    if(ex.name==='AbortError')throw new Error('伺服器回應逾時（15秒），請稍後重試');
    throw ex;
  }
}

/* ── 查詢任意股票 ── */
function tSearch(){
  mc('<div class="card"><div class="ct">🔍 查詢任意台股</div>'
    +edu("不限於監控清單，只需輸入4位股票代號即可查詢任何台灣上市/上櫃股票。"
      +"<br>可查：股價行情、三大法人籌碼、融資融券、示警。"
      +"<br>若是監控清單內的生技股，還會顯示 rNPV 估值和里程碑市值推估。")
    +'<div style="display:flex;gap:8px;margin-bottom:4px">'
    +'<input id="si" type="text" maxlength="6" placeholder="輸入代號，例如 2330" '
    +'style="flex:1;padding:10px 12px;border:2px solid #c5cae9;border-radius:8px;font-size:16px;outline:none"'
    +' onkeypress="if(event.key===\\\'Enter\\\')dSearch()">'
    +'<button onclick="dSearch()" style="background:#1a237e;color:white;border:none;'
    +'padding:10px 20px;border-radius:8px;font-size:15px;cursor:pointer;white-space:nowrap">查 詢</button>'
    +'</div>'
    +'<div style="font-size:11px;color:#aaa;margin-bottom:10px">⚠️ 需電腦連上台灣網路才能取得即時資料（週一~週五）</div>'
    +'<div id="sr"></div>'
    +'</div>');
}

async function dSearch(){
  var c=(document.getElementById("si")||{}).value||"";
  c=c.trim().toUpperCase();
  if(!c){return;}
  var sr=document.getElementById("sr");
  if(!sr)return;
  sr.innerHTML=ld("股票 "+c+" 資料（約10~30秒）");
  try{
    var d=await jget("/api/search/"+c);
    if(d.error){sr.innerHTML=nerr(d.error,d.hint);return;}
    var h="";
    var price=d.price,chg=price?(price.change||0):0;
    var cls=chg>0?"up":chg<0?"dn":"fl";
    // 股票標題
    h+='<div class="card" style="display:flex;justify-content:space-between;align-items:center">'
      +'<div><div style="font-size:20px;font-weight:700;color:#1a237e">'+d.code+'</div>'
      +'<div style="font-size:14px;color:#555">'+d.name+'</div>'
      +'<span class="badge '+(d.in_watchlist?"bb":"bg")+'">'+(d.in_watchlist?"🔬 監控清單":"📊 一般股票")+'</span>'
      +'</div>'
      +(price?'<div style="text-align:right"><div class="pb '+cls+'" style="font-size:28px">'+price.close+'</div>'
        +'<div class="'+cls+'" style="font-size:13px">'+(chg>0?"▲ +":chg<0?"▼ ":"─ ")+Math.abs(chg).toFixed(2)+" 元</div>"
        +'<div style="font-size:11px;color:#888">'+(price.date||"")+"</div></div>":"")
      +"</div>";
    // 三大法人
    var inst=(d.chip||{}).institutional||{};
    if(!inst.error){
      h+='<div class="card"><div class="ct">🏦 三大法人籌碼</div>'
        +"<table><tr><th>法人</th><th>今日淨買賣(張)</th><th>方向</th><th>連續天數</th><th>累計(張)</th></tr>"
        +["foreign","trust","dealer","total"].map(function(k){
          var lb={foreign:"外資",trust:"投信",dealer:"自營",total:"合計"}[k];
          var di=inst[k]||{},net=di.latest_net||0,cum=di.cumsum||0;
          return'<tr'+(k==="total"?' style="font-weight:700"':"")+">"
            +"<td>"+lb+"</td>"
            +'<td class="'+(net>0?"up":net<0?"dn":"")+'">'+fs(net)+"</td>"
            +"<td>"+(di.direction==="買超"?"📈 買":"📉 賣")+"</td>"
            +"<td>"+(di.consecutive||0)+"天</td>"
            +'<td class="'+(cum>0?"up":cum<0?"dn":"")+'">'+fs(cum)+"</td></tr>";
        }).join("")+"</table>"
        +(inst.signals||[]).map(function(s){return'<div style="margin-top:5px;font-size:13px">'+s+"</div>";}).join("")
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 籌碼資料暫時無法取得</p></div>';
    }
    // 示警
    if(d.alerts&&d.alerts.length){
      h+='<div class="card"><div class="ct">⚡ 示警</div>'
        +d.alerts.map(function(a){
          var c=a.level==="🔴"?"ad":a.level==="⚠️"?"aw":"ap";
          return'<div class="'+c+'">'+a.level+" "+a.msg+"</div>";
        }).join("")+"</div>";
    }
    // 估值（監控清單生技股才有）
    if(d.milestones){
      h+=rMilestone(d.milestones);
    }else if(!d.in_watchlist){
      h+='<div class="edu">ℹ️ 此股票不在監控清單，不顯示估值。'
        +'如需加入監控，請在 config.py 的 STOCKS 增加此代號。'
        +'<br>一般股票估值（本益比/EV/EBITDA）的自動計算功能後續版本將加入。</div>';
    }
    sr.innerHTML=h;
  }catch(e){
    if(document.getElementById("sr"))document.getElementById("sr").innerHTML=err(e.message);
  }
}
/* ── 新聞 ── */
async function tNews(){
  mc(ld("最新生技新聞（首次約30~60秒，需台灣網路）"));
  try{
    var d=await jcached("/api/news");
    var h=edu("<b>📰 新聞可信度由高到低：</b><br>"
      +"🔵 <b>主管機關</b>：FDA（美國）、TFDA（台灣食藥署）、ClinicalTrials.gov — 政府監管，造假違法，最可信<br>"
      +"🟢 <b>法定公開揭露</b>：MOPS重訊、法說會 — 公司<b>依法義務揭露</b>，說謊是刑事罪，可信度高<br>"
      +"🟡 <b>專業媒體</b>：STAT News、BioPharma Dive — 有編輯把關，生技圈權威媒體<br>"
      +"🟠 <b>一般財經媒體</b>：Reuters — 廣泛財經，生技報導深度較淺<br>"
      +"<br>⚠️ <b>怎麼判斷帶風向？</b>"
      +"<br>公司臨床本質未變卻出現負面報導，常見手法：誇大副作用、斷章取義數據、匿名「分析師」唱衰。"
      +"<br>→ 對照本工具「管線頁」的 ClinicalTrials.gov 官方登錄狀態：<b>官方試驗仍在進行 = 媒體唱衰沒根據</b>。");
    // ── 📅 里程碑進程提醒 ────────────────────────────
    var h2='';
    var cat_d=cache["/api/catalyst"]?cache["/api/catalyst"].data:null;
    if(!cat_d)try{cat_d=await jcached("/api/catalyst");}catch(ex){}
    if(cat_d){
      var allEvts=cat_d.events||[];
      var nowYear=new Date().getFullYear();
      // 有確定日期：未來60天內
      var defDates=allEvts.filter(function(e){return e.days_left!==null&&e.days_left>=0&&e.days_left<=60;});
      defDates.sort(function(a,b){return a.days_left-b.days_left;});
      // 模糊日期（Q/H/年份）：今年或明年
      var fuzzyDates=allEvts.filter(function(e){
        if(e.days_left!==null)return false;
        var yr=parseInt((e.date||"").substring(0,4));
        return yr===nowYear||yr===nowYear+1;
      });
      var combined=defDates.concat(fuzzyDates);
      if(combined.length){
        h2='<div class="card"><div class="ct">🔔 進程提醒：近期及年內里程碑（避免遺忘）</div>'
          +edu("🔴 今~7天 / ⚠️ 30天內 / ✅ 60天內 / 📅 年內模糊日期。<b>建議每週確認一次是否有最新消息。</b>");
        combined.forEach(function(e){
          var isFuzzy=e.days_left===null;
          var urg,badge,dateLabel;
          if(isFuzzy){
            urg="ap";badge="📅";
            dateLabel=e.date||"";
          }else{
            urg=e.days_left<=7?"ad":e.days_left<=30?"aw":"ap";
            badge=e.days_left<=7?"🔴":e.days_left<=30?"⚠️":"✅";
            var exact=e.date?'<span style="font-size:12px;font-weight:400;margin-right:6px">('+e.date+')</span>':"";
            dateLabel=exact+(e.days_left===0?'<span style="color:#e53935">今日！</span>':e.days_left+'天後');
          }
          h2+='<div class="'+urg+'" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">'
            +'<div><b>'+badge+' '+e.name+'('+e.code+')</b>'
            +'<div style="font-size:12px">'+e.description+'</div>'
            +(e.product?'<div style="font-size:11px;color:#888">'+e.product+'</div>':"")
            +'</div>'
            +'<div style="font-size:15px;font-weight:700;text-align:right;white-space:nowrap">'+dateLabel+'</div>'
            +'</div>';
        });
        h2+="</div>";
      }else{
        h2='<div class="card"><div class="ct">🔔 進程提醒</div>'
          +'<div style="color:#bbb;padding:12px;text-align:center;font-size:13px">近60天內無明確到期，今明年亦無模糊日期催化劑</div></div>';
      }
    }
    h=h2+h;  // 里程碑提醒放最上面
    // ── 🚨 重要解盲/臨床事件 ────────────────────────
    var flagged=(d.key_events||[]);
    if(flagged.length){
      h+='<div class="card"><div class="ct">🚨 重要臨床/解盲偵測事件（'+flagged.length+'則）</div>'
        +edu("自動掃描含「Phase 3 results、FDA approved、解盲、NDA核准」等關鍵字，高度影響股價。");
      flagged.forEach(function(e){
        var cls=e.alert_level==="high"?"ad":"aw";
        var lv=e.alert_level==="high"?"🔴 高重要性":"🟡 中重要性";
        var src=e.source||e.name||e.code||"";
        var ttl=e.title||e.subject||"（無標題）";
        var lnk=e.link||e.url||"#";
        h+='<div class="'+cls+'" style="margin-bottom:8px">'
          +'<div class="alb">'+lv+' · '+src+' · '+(e.pub_date||e.date||"").slice(0,16)+"</div>"
          +'<div style="font-weight:600"><a href="'+lnk+'" target="_blank" style="color:inherit">'+ttl+"</a></div>"
          +(e.summary?'<div style="font-size:12px;margin-top:3px;opacity:.85">'+e.summary.slice(0,160)+"...</div>":"")
          +"</div>";
      });
      h+="</div>";
    }
    // ── 🟢 法說會（法人說明會）────────────────────────
    var iconf=d.investor_conf||{};
    var confItems=[];
    stocks.forEach(function(s){
      var ci=(iconf[s.code]||{}).conferences||[];
      ci.forEach(function(c){confItems.push(Object.assign({},c,{sname:s.name,scode:s.code}));});
    });
    if(confItems.length){
      h+='<div class="card"><div class="ct">🟢 法人說明會（法說會）紀錄</div>'
        +edu("<b>法說會是最重要的一手資訊</b>：管理層親口說明臨床進度、資金狀況、策略。"
          +"<br>📄 依法必須上傳簡報PDF（點「查看附件」下載），有時附有錄影。"
          +"<br>🎥 <b>找影音</b>：點「MOPS法說會頁」→ 查看附件欄是否有影片連結；或至公司IR官網、YouTube搜尋「公司名稱 法說會」。");
      confItems.slice(0,8).forEach(function(c){
        var hasMat=c.material_url&&c.material_url.length>3;
        h+='<div class="ci" style="margin-bottom:8px">'
          +'<div class="cm"><span style="font-size:13px;font-weight:700">🟢 '+c.sname+'('+c.scode+')</span>'
          +'<span class="cdt">說明會日期：'+(c.conf_date||"")+"</span></div>"
          +'<div style="font-size:13px;margin:3px 0">'+(c.topic||"（無議題資訊）")+"</div>"
          +'<div style="font-size:11px;color:#888">方式：'+(c.method||"—")
          +(c.announce_date?' · 公告日：'+c.announce_date:"")+"</div>"
          +'<div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap">'
          +(hasMat?'<a href="'+c.material_url+'" target="_blank" style="font-size:12px;background:#e8f5e9;color:#2e7d32;padding:3px 10px;border-radius:12px;text-decoration:none">📄 查看附件/簡報</a>':"")
          +'<a href="'+c.mops_url+'" target="_blank" style="font-size:12px;background:#e3f2fd;color:#1565c0;padding:3px 10px;border-radius:12px;text-decoration:none">🔗 MOPS法說會頁</a>'
          +"</div></div>";
      });
      h+="</div>";
    }else{
      h+='<div class="card"><div class="ct">🟢 法人說明會（法說會）</div>'
        +'<div class="edu">⚠️ 法說會資料未能取得（可能是非交易時段或MOPS暫時無回應）。<br>'
        +'你可直接至 <a href="https://mops.twse.com.tw/mops/web/t100sb01" target="_blank">MOPS法說會專區</a> 輸入股票代號查詢。</div></div>';
    }
    // ── 🔵 FDA / TFDA 核准公告 ────────────────────────
    var fda=(d.fda_news||[]),tfda=(d.tfda_news||[]);
    if(fda.length||tfda.length){
      h+='<div class="card"><div class="ct">🔵 主管機關核准動態</div>'
        +edu("來源：FDA.gov（美國）+ TFDA（台灣食藥署）官方公告，最高可信度。");
      tfda.forEach(function(e){
        h+='<div class="ap" style="margin-bottom:7px">'
          +'<div class="alb">🔵 台灣TFDA食藥署 · '+(e.pub_date||"").slice(0,16)+"</div>"
          +'<div><a href="'+(e.link||"#")+'" target="_blank" style="color:#2e7d32;font-weight:600">'+e.title+"</a></div>"
          +(e.summary?'<div style="font-size:12px;color:#555;margin-top:2px">'+e.summary.slice(0,150)+"</div>":"")
          +"</div>";
      });
      fda.forEach(function(e){
        h+='<div class="ap" style="margin-bottom:7px">'
          +'<div class="alb">🔵 美國FDA官方 · '+(e.pub_date||"").slice(0,16)+"</div>"
          +'<div><a href="'+(e.link||"#")+'" target="_blank" style="color:#2e7d32;font-weight:600">'+e.title+"</a></div>"
          +(e.summary?'<div style="font-size:12px;color:#555;margin-top:2px">'+e.summary.slice(0,150)+"</div>":"")
          +"</div>";
      });
      h+="</div>";
    }
    // ── 🟢 MOPS 重大訊息 ────────────────────────────
    var mops=d.mops||{};
    var mopsItems=[];
    stocks.forEach(function(s){
      var items=mops[s.code]||[];
      items.forEach(function(e){mopsItems.push(Object.assign({},e,{sname:s.name,scode:s.code}));});
    });
    if(mopsItems.length){
      h+='<div class="card"><div class="ct">🟢 MOPS 重大訊息（法定公開揭露）</div>'
        +edu("公司依法義務揭露，說謊是刑事罪（證券交易法185條）。可信度 > 媒體報導。<br>"
          +"⚠️ 但留意：公告用字可能充滿公關語言，需配合管線頁的官方試驗資料綜合判斷。");
      mopsItems.slice(0,10).forEach(function(e){
        h+='<div class="ci" style="margin-bottom:6px">'
          +'<div class="cm"><span style="font-size:12px;font-weight:600">🟢 '+e.sname+'('+e.scode+')</span>'
          +'<span class="cdt">'+(e.pub_date||e.date||"")+"</span></div>"
          +'<div style="font-size:13px">'+(e.title||e.subject||"")+"</div>"
          +"</div>";
      });
      h+="</div>";
    }
    // ── 🟡 國際專業媒體 ────────────────────────────
    var intl=(d.intl_news||[]);
    if(intl.length){
      var srcBadge={"STAT News":"🟡","BioPharma Dive":"🟡","Reuters Health":"🟠","Reuters Biz":"🟠"};
      h+='<div class="card"><div class="ct">🟡 國際生技/財經媒體新聞</div>'
        +edu("STAT News、BioPharma Dive 是專業生技媒體，Reuters 是廣泛財經。"
          +"<br>讀到不利公司的報導，請先查 ClinicalTrials.gov 的官方試驗狀態再判斷。");
      intl.slice(0,10).forEach(function(e){
        var badge=srcBadge[e.source]||"🟠";
        h+='<div class="ci" style="margin-bottom:8px">'
          +'<div class="cm"><span style="font-size:12px;font-weight:600">'+badge+' '+(e.source||"")+"</span>"
          +'<span class="cdt">'+(e.pub_date||"").slice(0,16)+"</span></div>"
          +'<div style="font-size:13px"><a href="'+(e.link||"#")+'" target="_blank" style="color:#1a237e">'+e.title+"</a></div>"
          +(e.summary?'<div class="cno" style="font-size:11px">'+e.summary.slice(0,130)+"...</div>":"")
          +"</div>";
      });
      h+="</div>";
    }
    if(!flagged.length&&!confItems.length&&!intl.length&&!fda.length&&!tfda.length&&!mopsItems.length){
      h+='<div class="empty">📭 暫無新聞資料<br><span style="font-size:12px;color:#bbb">請確認已連上網路（週一~週五台股時段效果最佳）</span></div>';
    }
    h+='<div style="font-size:11px;color:#bbb;text-align:right;padding:4px">新聞更新時間：'+(d.updated||"未知")+"</div>";
    mc(h);
  }catch(e){mc(err("新聞抓取失敗："+e.message+"<br><small style='color:#888'>請確認已連上台灣網路，或稍候重試</small>"));}
}
init();
"""


@app.get('/js/app.js')
async def serve_js():
    from fastapi.responses import Response
    return Response(content=_JS_CODE, media_type='application/javascript; charset=utf-8')

def main():
    parser = argparse.ArgumentParser(description='生技股分析網頁伺服器')
    parser.add_argument('--mobile', action='store_true',
                        help='開放區域網路（手機同一WiFi可連）')
    parser.add_argument('--port', type=int, default=8000, help='埠號（預設8000）')
    args = parser.parse_args()

    host = '0.0.0.0' if args.mobile else '127.0.0.1'

    print('=' * 56)
    print('  🔬 台灣生技股分析儀表板 已啟動')
    print()
    if args.mobile:
        print('  📱 手機可連模式（同一 WiFi）：')
        _print_ip(args.port)
    else:
        print(f'  💻 電腦瀏覽器開啟：http://localhost:{args.port}')
        print()
        print('  提示：想讓手機連線請改用：python web_server.py --mobile')
    print()
    print(f'  🔐 帳號：{WEB_USERNAME}  密碼：{WEB_PASSWORD}')
    print()
    print('  ✅ 催化劑日曆（快速）')
    print('  ✅ 三大法人籌碼 / 融資融券（需台灣IP）')
    print('  ✅ rNPV估值分析（本地計算，快速）')
    print('  ✅ 示警系統')
    print('  ✅ 研發管線總覽')
    print('  ✅ 新聞追蹤（國際生技/FDA/解盲偵測）')
    print()
    print('  按 Ctrl+C 停止')
    print('=' * 56)

    uvicorn.run(app, host=host, port=args.port, log_level='warning')


def _print_ip(port: int) -> None:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        print(f'  手機瀏覽器開啟：http://{ip}:{port}')
        print(f'  電腦也可用：    http://localhost:{port}')
    except Exception:
        print(f'  手機瀏覽器開啟：http://電腦IP:{port}')
        print('  （先在命令提示字元輸入 ipconfig 查看電腦 IP）')
    print()


if __name__ == '__main__':
    main()
