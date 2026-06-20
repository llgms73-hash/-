"""
新聞與臨床資料自動抓取模組
來源：
  - ClinicalTrials.gov API（公開）    → 臨床試驗詳情 / 解盲進度
  - FDA.gov RSS（公開）               → 新藥核准公告
  - MOPS 公開資訊觀測站（台灣）       → 重大訊息 / 法說會
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
    url = 'https://www.fda.gov/about-fda/contact-fda/rss-feeds-fda'
    # FDA藥物核准 RSS
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


# ── 國際生技新聞 RSS ───────────────────────────────────────────

_NEWS_SOURCES = [
    # (名稱, RSS URL, 分類)
    ('STAT News',      'https://www.statnews.com/feed/',                    '全球生技'),
    ('BioPharma Dive', 'https://www.biopharmadive.com/feeds/news/',         '全球生技'),
    ('Reuters Health', 'https://feeds.reuters.com/reuters/healthNews',      '財經/健康'),
    ('Reuters Biz',    'https://feeds.reuters.com/reuters/businessNews',    '國際財經'),
]


def get_intl_news(categories: list[str] = None, max_per_source: int = 5) -> list[dict]:
    """
    從多個公開 RSS 取得國際財經 / 生技新聞
    categories: ['全球生技', '國際財經'] 若為 None 則全取
    """
    all_news = []
    for (source, url, cat) in _NEWS_SOURCES:
        if categories and cat not in categories:
            continue
        text = _get(url, timeout=10)
        if not text or not isinstance(text, str):
            continue
        items = _parse_rss(text, max_per_source)
        for item in items:
            item['source'] = source
            item['category'] = cat
        all_news.extend(items)
        time.sleep(0.3)

    # 按發佈時間降序排列
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
                'source':   'MOPS',
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
        # 移除可能造成解析問題的字元
        text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', text)
        root = ET.fromstring(text)

        # 標準 RSS 2.0
        items = root.findall('.//item')
        # Atom feed
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

            # 清除 HTML 標籤
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
    包含：國際生技/財經新聞、FDA核准、ClinicalTrials更新、台灣重大訊息
    """
    print('  抓取國際生技新聞...')
    intl = get_intl_news(max_per_source=5)

    print('  抓取 FDA 核准公告...')
    fda = get_fda_approvals(max_items=5)

    print('  抓取 MOPS 重大訊息...')
    mops = get_mops_news_all()

    # 偵測解盲/臨床關鍵事件
    all_news = intl + fda
    flagged = detect_unblinding_keywords(all_news)

    # 整合 MOPS 重大訊息也偵測關鍵字
    for code, news_list in mops.items():
        flagged_mops = detect_unblinding_keywords(news_list)
        for item in flagged_mops:
            item['code'] = code
            item['name'] = STOCKS.get(code, {}).get('name', code)
            flagged.append(item)

    return {
        'intl_news':    intl,
        'fda_news':     fda,
        'mops':         mops,
        'key_events':   flagged,
        'updated':      datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
