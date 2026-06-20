"""
新聞與臨床資料自動抓取模組
來源：
  - ClinicalTrials.gov API（公開）    → 臨床試驗詳情 / 解盲進度
  - FDA.gov RSS（公開）               → 新藥核准公告
  - TFDA RSS（台灣食藥署）            → 台灣新藥查驗登記動態
  - MOPS 公開資訊觀測站（台灣）       → 重大訊息 / 法說會公告 / 附件
  - Reuters RSS（公開）               → 國際財經新聞
  - STAT News RSS（公開）             → 全球生技新聞
"""

import time
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from config import REQUEST_HEADERS, REQUEST_TIMEOUT, RETRY_TIMES, RETRY_DELAY, STOCKS, PIPELINE


def _get(url: str, params: dict = None, timeout: int = None) -> dict | str | None:
    headers = dict(REQUEST_HEADERS)
    try:
        resp = requests.get(url, params=params, headers=headers,
                            timeout=timeout or REQUEST_TIMEOUT)
        resp.raise_for_status()
        ct = resp.headers.get('Content-Type', '')
        if 'json' in ct:
            return resp.json()
        return resp.text
    except Exception as e:
        print(f'  [news_fetcher] {url[:60]}... → {e}')
        return None


def _get_mops(url: str, params: dict) -> dict | None:
    """MOPS 專用 GET，加上必要的 Referer"""
    headers = dict(REQUEST_HEADERS)
    headers['Referer'] = 'https://mops.twse.com.tw/'
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
    except Exception as e:
        print(f'  [MOPS] {url[:60]}... → {e}')
    return None


def _safe(row: list, idx: int, default: str = '') -> str:
    try:
        v = row[idx]
        return v.strip() if isinstance(v, str) else (str(v) if v is not None else default)
    except (IndexError, AttributeError):
        return default


# ── ClinicalTrials.gov API ──────────────────────────────────────

def get_ct_trials(nct_ids: list[str] = None, company: str = None,
                  max_results: int = 10) -> list[dict]:
    """
    從 ClinicalTrials.gov API 取得臨床試驗資料
    可用 NCT 編號 或 公司名稱 查詢

    回傳欄位：
      nct_id, title, status, phase, condition, sponsor,
      start_date, completion_date, enrollment, last_update
    """
    base_url = 'https://clinicaltrials.gov/api/v2/studies'

    if nct_ids:
        query = ' OR '.join(nct_ids)
        params = {'query.id': query, 'pageSize': max_results, 'format': 'json'}
    elif company:
        params = {'query.term': company, 'pageSize': max_results,
                  'query.spons': company, 'format': 'json'}
    else:
        return []

    data = _get(base_url, params=params)
    if not data or not isinstance(data, dict):
        return []

    results = []
    for study in data.get('studies', []):
        proto = study.get('protocolSection', {})
        id_mod = proto.get('identificationModule', {})
        status_mod = proto.get('statusModule', {})
        design_mod = proto.get('designModule', {})
        cond_mod = proto.get('conditionsModule', {})
        sponsor_mod = proto.get('sponsorCollaboratorsModule', {})

        phases = design_mod.get('phases', [])
        phase_str = '/'.join(p.replace('PHASE', 'Phase').replace('_', '') for p in phases) if phases else 'N/A'

        results.append({
            'nct_id':          id_mod.get('nctId', ''),
            'title':           id_mod.get('briefTitle', ''),
            'status':          status_mod.get('overallStatus', ''),
            'phase':           phase_str,
            'conditions':      cond_mod.get('conditions', []),
            'sponsor':         sponsor_mod.get('leadSponsor', {}).get('name', ''),
            'start_date':      status_mod.get('startDateStruct', {}).get('date', ''),
            'completion_date': status_mod.get('primaryCompletionDateStruct', {}).get('date', ''),
            'enrollment':      design_mod.get('enrollmentInfo', {}).get('count'),
            'last_update':     status_mod.get('lastUpdateSubmitDate', ''),
            'url': f"https://clinicaltrials.gov/study/{id_mod.get('nctId', '')}",
        })

    return results


def get_all_monitored_trials() -> dict[str, list[dict]]:
    """抓取所有監控股票的 ClinicalTrials.gov 資料"""
    results = {}

    # 公司名稱關鍵字對應（用於 CT.gov 搜尋）
    company_keywords = {
        '7827': ['HanchorBio', 'Hanchor', 'HCB101'],
        '6919': ['Caliway', 'CBL-514'],
        '6467': ['Taho', 'TAH3311'],
        '6917': ['Andros', 'APC201', 'APC101'],
    }

    for code, keywords in company_keywords.items():
        name = STOCKS.get(code, {}).get('name', code)
        all_trials = []
        for kw in keywords[:2]:  # 只搜前兩個關鍵字，避免過多請求
            trials = get_ct_trials(company=kw, max_results=5)
            for t in trials:
                if not any(x['nct_id'] == t['nct_id'] for x in all_trials):
                    all_trials.append(t)
            time.sleep(0.5)
        results[code] = {'name': name, 'trials': all_trials}

    return results


# ── FDA 新藥核准 RSS ────────────────────────────────────────────

def get_fda_approvals(max_items: int = 10) -> list[dict]:
    """從 FDA RSS 取得最新核准藥物公告"""
    rss_urls = [
        'https://www.fda.gov/rss/drugs-approvals.xml',
        'https://www.fda.gov/rss/drugs-new-drug-approvals.xml',
    ]

    results = []
    for rss_url in rss_urls:
        text = _get(rss_url, timeout=10)
        if not text or not isinstance(text, str):
            continue
        items = _parse_rss(text, max_items)
        results.extend(items)
        if results:
            break

    return results[:max_items]


# ── TFDA 台灣食藥署 ────────────────────────────────────────────

def get_tfda_news(max_items: int = 10) -> list[dict]:
    """從 TFDA 台灣食藥署取得最新藥品查驗/核准動態"""
    # TFDA 開放資料 RSS / API
    urls = [
        'https://www.fda.gov.tw/RSS/news_rss.aspx?nodeID=323',   # 藥品查驗登記
        'https://www.fda.gov.tw/RSS/news_rss.aspx?nodeID=322',   # 藥物安全快訊
    ]
    results = []
    for url in urls:
        text = _get(url, timeout=10)
        if not text or not isinstance(text, str):
            continue
        items = _parse_rss(text, max_items)
        for item in items:
            item['source'] = 'TFDA'
        results.extend(items)
        time.sleep(0.3)
    return results[:max_items]


# ── MOPS 法人說明會（法說會）─────────────────────────────────

def get_investor_conferences(code: str, years_back: int = 2) -> list[dict]:
    """
    從 MOPS 取得公司法人說明會（法說會）公告
    回傳：公告日期、說明會日期、議題、說明方式、附件連結

    法說會是生技股最重要的資訊來源之一：
    - 管理層親口說明臨床進度、資金狀況、策略調整
    - 依法義務上傳簡報 PDF（可直接下載）
    - 有時附有錄影（需至附件或公司IR頁面找）
    """
    results = []
    current_year = datetime.now().year

    for yr in range(current_year, current_year - years_back - 1, -1):
        roc_year = yr - 1911
        data = _get_mops('https://mops.twse.com.tw/mops/web/ajax_t100sb01', params={
            'encodeURIComponent': '1', 'step': '1', 'firstin': '1', 'off': '1',
            'co_id': code, 'year': str(roc_year), 'TYPEK': 'all', 'pgnum': '1',
        })
        if not data or not isinstance(data, dict):
            time.sleep(0.3)
            continue

        for row in data.get('data', []):
            if not isinstance(row, list) or len(row) < 4:
                continue
            # MOPS t100sb01 欄位：公告日、公司代號、公司名、說明會日期、方式、議題、附件
            conf_date = _safe(row, 3) or _safe(row, 2)
            topic = _safe(row, 5) or _safe(row, 4)
            material = _safe(row, 6) or ''
            results.append({
                'announce_date': _safe(row, 0),
                'conf_date':     conf_date,
                'method':        _safe(row, 4),
                'topic':         topic,
                'material_url':  material,
                'source':        'MOPS法說會',
                'code':          code,
                'mops_url': f'https://mops.twse.com.tw/mops/web/t100sb01?co_id={code}',
            })
        time.sleep(0.3)

    # 依說明會日期降序
    results.sort(key=lambda x: x.get('conf_date', ''), reverse=True)
    return results


def get_all_investor_conferences() -> dict[str, list[dict]]:
    """取得所有監控股票的法說會資料"""
    results = {}
    for code, info in STOCKS.items():
        confs = get_investor_conferences(code, years_back=2)
        results[code] = {'name': info['name'], 'conferences': confs}
        time.sleep(0.5)
    return results


# ── 國際生技新聞 RSS ───────────────────────────────────────────

_NEWS_SOURCES = [
    # (名稱, RSS URL, 分類, 可信度)
    ('STAT News',      'https://www.statnews.com/feed/',                    '全球生技', 'pro'),
    ('BioPharma Dive', 'https://www.biopharmadive.com/feeds/news/',         '全球生技', 'pro'),
    ('Reuters Health', 'https://feeds.reuters.com/reuters/healthNews',      '財經/健康', 'gen'),
    ('Reuters Biz',    'https://feeds.reuters.com/reuters/businessNews',    '國際財經', 'gen'),
]


def get_intl_news(categories: list[str] = None, max_per_source: int = 5) -> list[dict]:
    """
    從多個公開 RSS 取得國際財經 / 生技新聞
    categories: ['全球生技', '國際財經'] 若為 None 則全取
    """
    all_news = []
    for (source, url, cat, cred) in _NEWS_SOURCES:
        if categories and cat not in categories:
            continue
        text = _get(url, timeout=10)
        if not text or not isinstance(text, str):
            continue
        items = _parse_rss(text, max_per_source)
        for item in items:
            item['source'] = source
            item['category'] = cat
            item['credibility'] = cred  # 'pro'=專業媒體 / 'gen'=一般財經
        all_news.extend(items)
        time.sleep(0.3)

    all_news.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
    return all_news


# ── MOPS 重大訊息（台灣）─────────────────────────────────────

def get_mops_news_all(days_back: int = 7) -> dict[str, list[dict]]:
    """
    取得監控清單所有股票的 MOPS 重大訊息
    回傳 {code: [訊息列表]}，格式已標準化供 detect_unblinding_keywords 使用
    """
    from fetcher import get_major_news
    results = {}
    for code in STOCKS:
        raw = get_major_news(code)
        # 標準化為 detect_unblinding_keywords 可讀的格式
        normalized = [
            {
                'title':    n.get('subject', ''),
                'link':     n.get('url', ''),
                'pub_date': n.get('date', ''),
                'summary':  '',
                'source':   'MOPS重訊',
                'code':     n.get('code', code),
            }
            for n in raw
        ]
        results[code] = normalized
        time.sleep(0.5)
    return results


# ── 解盲事件偵測 ──────────────────────────────────────────────

def detect_unblinding_keywords(news_items: list[dict]) -> list[dict]:
    """
    在新聞標題/內容中偵測臨床解盲/數據公布相關關鍵字
    回傳符合的新聞，並標注重要程度
    """
    keywords_high = [
        'topline', 'top-line', 'primary endpoint', 'phase 3 results',
        'phase 2 results', 'clinical trial results', 'unblinded', 'unblinding',
        'pivotal trial', 'pdufa', 'nda approved', 'fda approved', 'fda approval',
        '解盲', '臨床結果', '頂線數據', 'NDA核准', 'FDA核准',
        '三期成功', '二期成功', '主要療效終點',
    ]
    keywords_med = [
        'interim analysis', 'data readout', 'trial update', 'ind', 'ind filing',
        'phase 2', 'phase 3', 'enrollment complete', 'fully enrolled',
        '期中分析', '完成收案', '送件', '重大訊息',
    ]

    flagged = []
    for item in news_items:
        text = (item.get('title', '') + ' ' + item.get('summary', '')).lower()
        level = None
        for kw in keywords_high:
            if kw.lower() in text:
                level = 'high'
                break
        if not level:
            for kw in keywords_med:
                if kw.lower() in text:
                    level = 'medium'
                    break
        if level:
            flagged.append({**item, 'alert_level': level})

    return flagged


# ── RSS 解析工具 ───────────────────────────────────────────────

def _parse_rss(text: str, max_items: int = 10) -> list[dict]:
    """解析 RSS XML，回傳標準化的新聞列表"""
    results = []
    try:
        text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', text)
        root = ET.fromstring(text)

        items = root.findall('.//item')
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        if not items:
            items = root.findall('.//atom:entry', ns)

        for item in items[:max_items]:
            def get_text(tag, ns_map=None):
                el = item.find(tag) if not ns_map else item.find(tag, ns_map)
                return el.text.strip() if el is not None and el.text else ''

            title   = get_text('title') or get_text('atom:title', ns)
            link    = get_text('link') or get_text('atom:link', ns)
            summary = get_text('description') or get_text('atom:summary', ns)
            pub     = get_text('pubDate') or get_text('atom:updated', ns)

            summary = re.sub(r'<[^>]+>', '', summary)[:300]

            if title:
                results.append({
                    'title':    title,
                    'link':     link,
                    'summary':  summary,
                    'pub_date': pub,
                })
    except Exception as e:
        print(f'  [RSS parse error] {e}')
    return results


# ── 整合函式：取得所有最新資訊 ────────────────────────────────

def get_full_news_update() -> dict:
    """
    一次性取得所有新聞來源的最新資訊
    包含：國際生技/財經新聞、FDA核准、TFDA台灣動態、
          法人說明會公告、台灣重大訊息、解盲偵測
    """
    print('  抓取國際生技新聞...')
    intl = get_intl_news(max_per_source=5)

    print('  抓取 FDA 核准公告...')
    fda = get_fda_approvals(max_items=5)

    print('  抓取 TFDA 台灣食藥署動態...')
    tfda = get_tfda_news(max_items=5)

    print('  抓取 MOPS 重大訊息...')
    mops = get_mops_news_all()

    print('  抓取法人說明會（法說會）公告...')
    investor_conf = get_all_investor_conferences()

    # 偵測解盲/臨床關鍵事件
    all_news = intl + fda + tfda
    flagged = detect_unblinding_keywords(all_news)

    # MOPS 重大訊息也偵測關鍵字
    for code, news_list in mops.items():
        flagged_mops = detect_unblinding_keywords(news_list)
        for item in flagged_mops:
            item['code'] = code
            item['name'] = STOCKS.get(code, {}).get('name', code)
            flagged.append(item)

    return {
        'intl_news':      intl,
        'fda_news':       fda,
        'tfda_news':      tfda,
        'mops':           mops,
        'investor_conf':  investor_conf,
        'key_events':     flagged,
        'updated':        datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

