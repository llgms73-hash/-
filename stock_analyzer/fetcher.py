"""
資料抓取模組 - 從台灣 TWSE / TPEx 合法開放 API 取得資料
支援：股價、三大法人、融資融券、重大訊息
"""

import time
import json
import requests
import concurrent.futures
from datetime import datetime, timedelta
from config import REQUEST_HEADERS, REQUEST_TIMEOUT, RETRY_TIMES, RETRY_DELAY


def _get(url: str, params: dict = None, referer: str = None) -> dict | list | None:
    headers = dict(REQUEST_HEADERS)
    if referer:
        headers['Referer'] = referer

    for attempt in range(RETRY_TIMES):
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            ct = resp.headers.get('Content-Type', '')
            if 'json' in ct:
                return resp.json()
            text = resp.text.strip()
            if text.startswith(('{', '[')):
                return json.loads(text)
            return {'raw': text}
        except requests.HTTPError as e:
            print(f"  [HTTP {e.response.status_code}] {url}")
            return None
        except Exception as e:
            if attempt < RETRY_TIMES - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [ERROR] {url} → {e}")
                return None
    return None


def _last_trading_day(offset: int = 0) -> str:
    """取得最近交易日（跳過週末），offset=0 為最近一個交易日"""
    d = datetime.today() - timedelta(days=offset)
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d.strftime('%Y%m%d')


def _tpex_date(date_str: str) -> str:
    """將 YYYYMMDD 轉為 TPEx 用的 YYYY/MM/DD"""
    return f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"


# ── 股價資料 ──────────────────────────────────────────────────

def get_twse_price(code: str, date: str = None) -> dict | None:
    """從 TWSE 取得個股日收盤資料（上市股用）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY'
    data = _get(url, params={'response': 'json', 'date': date, 'stockNo': code},
                referer='https://www.twse.com.tw/')
    if not data or data.get('stat') != 'OK':
        return None
    fields = data.get('fields', [])
    rows = data.get('data', [])
    if not rows:
        return None
    latest = rows[-1]
    result = dict(zip(fields, latest))
    return {
        'code': code,
        'date': result.get('日期', ''),
        'open': _parse_num(result.get('開盤價')),
        'high': _parse_num(result.get('最高價')),
        'low': _parse_num(result.get('最低價')),
        'close': _parse_num(result.get('收盤價')),
        'volume': _parse_num(result.get('成交股數')),
        'change': _parse_num(result.get('漲跌價差')),
        'source': 'TWSE',
    }


def get_tpex_price(code: str, date: str = None) -> dict | None:
    """從 TPEx 取得個股日收盤資料（上櫃股用）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php'
    data = _get(url, params={
        'l': 'zh-tw', 'd': _tpex_date(date),
        's': '0,asc,0', '_': str(int(time.time() * 1000))
    }, referer='https://www.tpex.org.tw/')
    if not data:
        return None
    rows = data.get('aaData', [])
    for row in rows:
        # row[0] = 代號, row[1] = 名稱, row[2] = 收盤, ...
        if str(row[0]).strip() == code:
            return {
                'code': code,
                'date': date,
                'close': _parse_num(row[2]),
                'change': _parse_num(row[3]),
                'open': _parse_num(row[4]),
                'high': _parse_num(row[5]),
                'low': _parse_num(row[6]),
                'volume': _parse_num(row[8]),
                'source': 'TPEx',
            }
    return None


def get_emerging_price(code: str, date: str = None) -> dict | None:
    """從 TPEx 取得興櫃股價資料"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.tpex.org.tw/web/emergingstock/emerging_stk_quote.php'
    data = _get(url, params={
        'l': 'zh-tw', 'd': _tpex_date(date),
        '_': str(int(time.time() * 1000))
    }, referer='https://www.tpex.org.tw/')
    if not data:
        return None
    rows = data.get('aaData', [])
    for row in rows:
        if str(row[0]).strip() == code:
            return {
                'code': code,
                'date': date,
                'close': _parse_num(row[3]),
                'open': _parse_num(row[4]),
                'high': _parse_num(row[5]),
                'low': _parse_num(row[6]),
                'volume': _parse_num(row[10]),
                'source': 'Emerging',
            }
    return None


def get_price(code: str, date: str = None) -> dict | None:
    """自動嘗試 TPEx → TWSE → 興櫃"""
    price = get_tpex_price(code, date)
    if price:
        return price
    price = get_twse_price(code, date)
    if price:
        return price
    return get_emerging_price(code, date)


def get_price_history(code: str, days: int = 60) -> list[dict]:
    """取得近 N 個交易日的股價（並行抓取，大幅加速）"""
    candidate_dates = [_last_trading_day(i) for i in range(days * 2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(candidate_dates))) as ex:
        futures = {ex.submit(get_price, code, d): d for d in candidate_dates}
        raw = [f.result() for f in concurrent.futures.as_completed(futures)]
    results = sorted([r for r in raw if r], key=lambda x: x.get('date', ''))
    return results[-days:]


# ── 三大法人 ──────────────────────────────────────────────────

def get_tpex_institutional(code: str, date: str = None) -> dict | None:
    """TPEx 三大法人買賣超（上櫃）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php'
    data = _get(url, params={
        'l': 'zh-tw', 't': 'D', 'd': _tpex_date(date),
        's': '0,asc', '_': str(int(time.time() * 1000))
    }, referer='https://www.tpex.org.tw/')
    if not data:
        return None
    rows = data.get('aaData', [])
    for row in rows:
        if str(row[0]).strip() == code:
            # row: 代號,名稱,外資買,外資賣,外資淨,投信買,投信賣,投信淨,自營買,自營賣,自營淨,合計淨...
            return {
                'code': code,
                'date': date,
                'foreign_net': _parse_int(row[4]),
                'trust_net':   _parse_int(row[7]),
                'dealer_net':  _parse_int(row[10]),
                'total_net':   _parse_int(row[11]) if len(row) > 11 else (
                    _parse_int(row[4]) + _parse_int(row[7]) + _parse_int(row[10])
                ),
                'source': 'TPEx',
            }
    return None


def get_twse_institutional(code: str, date: str = None) -> dict | None:
    """TWSE 三大法人買賣超（上市）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.twse.com.tw/fund/T86'
    data = _get(url, params={
        'response': 'json', 'date': date, 'selectType': 'ALL'
    }, referer='https://www.twse.com.tw/')
    if not data or data.get('stat') != 'OK':
        return None
    fields = data.get('fields', [])
    for row in data.get('data', []):
        if str(row[0]).strip() == code:
            r = dict(zip(fields, row))
            return {
                'code': code,
                'date': date,
                'foreign_net': _parse_int(r.get('外陸資買賣超股數(不含外資自營商)', '0')),
                'trust_net':   _parse_int(r.get('投信買賣超股數', '0')),
                'dealer_net':  _parse_int(r.get('自營商買賣超股數', '0')),
                'total_net':   _parse_int(r.get('三大法人買賣超股數', '0')),
                'source': 'TWSE',
            }
    return None


def get_institutional(code: str, date: str = None) -> dict | None:
    data = get_tpex_institutional(code, date)
    if data:
        return data
    return get_twse_institutional(code, date)


def get_institutional_history(code: str, days: int = 20) -> list[dict]:
    candidate_dates = [_last_trading_day(i) for i in range(days * 2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(candidate_dates))) as ex:
        futures = {ex.submit(get_institutional, code, d): d for d in candidate_dates}
        raw = [f.result() for f in concurrent.futures.as_completed(futures)]
    results = sorted([r for r in raw if r], key=lambda x: x.get('date', ''))
    return results[-days:]


# ── 融資融券 ──────────────────────────────────────────────────

def get_tpex_margin(code: str, date: str = None) -> dict | None:
    """TPEx 融資融券餘額（上櫃）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php'
    data = _get(url, params={
        'l': 'zh-tw', 'd': _tpex_date(date),
        's': '0,asc', '_': str(int(time.time() * 1000))
    }, referer='https://www.tpex.org.tw/')
    if not data:
        return None
    rows = data.get('aaData', [])
    for row in rows:
        if str(row[0]).strip() == code:
            # 典型欄位：代號,名稱,融資買進,融資賣出,現金償還,融資餘額,融資限額,
            #           融券賣出,融券買進,現券償還,融券餘額,融券限額,...
            margin_bal  = _parse_int(row[5])
            margin_lim  = _parse_int(row[6]) or 1
            short_bal   = _parse_int(row[10])
            short_ratio = round(short_bal / margin_bal * 100, 2) if margin_bal else 0
            usage_rate  = round(margin_bal / margin_lim * 100, 2) if margin_lim else 0
            return {
                'code': code,
                'date': date,
                'margin_buy':    _parse_int(row[2]),
                'margin_sell':   _parse_int(row[3]),
                'margin_bal':    margin_bal,
                'margin_limit':  margin_lim,
                'margin_usage':  usage_rate,
                'short_sell':    _parse_int(row[7]),
                'short_buy':     _parse_int(row[8]),
                'short_bal':     short_bal,
                'short_ratio':   short_ratio,
                'source': 'TPEx',
            }
    return None


def get_twse_margin(code: str, date: str = None) -> dict | None:
    """TWSE 融資融券餘額（上市）"""
    if not date:
        date = _last_trading_day()
    url = 'https://www.twse.com.tw/exchangeReport/MI_MARGN'
    data = _get(url, params={
        'response': 'json', 'date': date, 'selectType': 'ALL'
    }, referer='https://www.twse.com.tw/')
    if not data or data.get('stat') != 'OK':
        return None
    for section in ['融資', '融券']:
        pass
    fields = data.get('fields', [])
    for row in data.get('data', []):
        if str(row[0]).strip() == code:
            r = dict(zip(fields, row))
            margin_bal = _parse_int(r.get('融資餘額', '0'))
            short_bal  = _parse_int(r.get('融券餘額', '0'))
            return {
                'code': code,
                'date': date,
                'margin_bal':  margin_bal,
                'short_bal':   short_bal,
                'short_ratio': round(short_bal / margin_bal * 100, 2) if margin_bal else 0,
                'source': 'TWSE',
            }
    return None


def get_margin(code: str, date: str = None) -> dict | None:
    data = get_tpex_margin(code, date)
    if data:
        return data
    return get_twse_margin(code, date)


def get_margin_history(code: str, days: int = 20) -> list[dict]:
    candidate_dates = [_last_trading_day(i) for i in range(days * 2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(candidate_dates))) as ex:
        futures = {ex.submit(get_margin, code, d): d for d in candidate_dates}
        raw = [f.result() for f in concurrent.futures.as_completed(futures)]
    results = sorted([r for r in raw if r], key=lambda x: x.get('date', ''))
    return results[-days:]


# ── 重大訊息（公開資訊觀測站）────────────────────────────────

def get_major_news(code: str) -> list[dict]:
    """抓取公開資訊觀測站重大訊息（近 30 筆）"""
    url = 'https://mops.twse.com.tw/mops/web/ajax_t05st01'
    data = _get(url, params={
        'encodeURIComponent': '1', 'step': '1',
        'firstin': '1', 'off': '1', 'keyword4': '',
        'code1': '', 'TYPEK2': '', 'checkbtn': '',
        'queryName': 'co_id', 'inpuType': 'co_id',
        'TYPEK': 'all', 'isnew': 'false',
        'co_id': code, 'begin_dt': '', 'end_dt': '',
        'pgnum': '1',
    }, referer='https://mops.twse.com.tw/')
    if not data:
        return []
    items = []
    for row in data.get('data', []):
        if len(row) >= 4:
            items.append({
                'date':    row[0],
                'code':    row[1],
                'subject': row[3],
                'url':     row[4] if len(row) > 4 else '',
            })
    return items[:30]


# ── 工具函式 ──────────────────────────────────────────────────

def _parse_num(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(str(val).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0
