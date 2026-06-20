"""
催化劑日曆模組
追蹤生技股最重要的事件驅動時間點：
- PDUFA / NDA 送件日期
- 臨床試驗結果預計公布日
- 法說會 / 重大訊息
- 授權交易更新
- 財報公布日
"""

from datetime import datetime, timedelta


# ── 催化劑事件資料庫（需依公司公告手動維護）────────────────────
# 資料來源：公司 IR 簡報、重大訊息、ClinicalTrials.gov、法說會記錄
#
# event_type 分類：
#   'trial_result'  → 臨床試驗結果公布（最高影響）
#   'fda_action'    → FDA/TFDA 審批決定（最高影響）
#   'bd_deal'       → 授權/合作交易更新（高影響）
#   'earnings'      → 季報/年報公布（中影響）
#   'conference'    → 醫學年會發表數據（中影響）
#   'milestone'     → 里程碑付款/進入下一期（高影響）
#   'cash_raise'    → 現金增資/私募（高影響，通常負面）
#   'other'         → 其他重要事件
#
# impact：'high' / 'medium' / 'low'
# direction：'positive' / 'negative' / 'binary'（不確定方向）

CATALYSTS = {
    '7827': {  # 康霈
        'company_basics': {
            'shares_mn': None,       # 流通股數（百萬股），從財報取得
            'listing_date': None,    # 掛牌日
            'ir_page': '',           # IR 官網
            'clinical_trials_ids': [],  # ClinicalTrials.gov NCT 編號列表
        },
        'events': [
            # 範例格式（請依公司公告填入）：
            # {
            #     'date': '2026-Q3',       # 具體日期或季度
            #     'event_type': 'trial_result',
            #     'product': '產品代號',
            #     'description': '第二期臨床試驗頂線數據公布',
            #     'impact': 'high',
            #     'direction': 'binary',
            #     'notes': '成功則股價可能+30%～+80%；失敗則-40%～-70%',
            # },
        ],
    },
    '6919': {  # 漢康-KY
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': '',
            'clinical_trials_ids': [],
        },
        'events': [],
    },
    '6467': {  # 泰合
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': '',
            'clinical_trials_ids': [],
        },
        'events': [],
    },
    '6917': {  # 竟天
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': '',
            'clinical_trials_ids': [],
        },
        'events': [],
    },
}

# ── 國際醫學年會時間表（生技股重要發表場合）──────────────────────
# 這些年會是生技股最容易出現數據驅動行情的時間點
MAJOR_CONFERENCES_2026 = [
    {'name': 'ASCO',         'full': '美國臨床腫瘤學會年會',    'period': '2026-05-29/06-02', 'focus': '癌症'},
    {'name': 'EHA',          'full': '歐洲血液學年會',          'period': '2026-06-11/06-14', 'focus': '血液腫瘤'},
    {'name': 'ADA',          'full': '美國糖尿病學會年會',      'period': '2026-06-19/06-23', 'focus': '代謝疾病'},
    {'name': 'ISMRM',        'full': '國際磁振造影年會',        'period': '2026-05-03/05-08', 'focus': '影像醫學'},
    {'name': 'ESC',          'full': '歐洲心臟學會年會',        'period': '2026-08-28/09-01', 'focus': '心血管'},
    {'name': 'ESMO',         'full': '歐洲腫瘤醫學學會年會',    'period': '2026-09-12/09-16', 'focus': '癌症'},
    {'name': 'AASLD',        'full': '美國肝病學會年會',        'period': '2026-11 TBD',      'focus': '肝病'},
    {'name': 'ASH',          'full': '美國血液學年會',          'period': '2026-12-05/12-08', 'focus': '血液腫瘤'},
    {'name': 'JPM Healthcare','full': 'JP Morgan 醫療健康年會', 'period': '2027-01 TBD',      'focus': '產業/BD 交易'},
    {'name': 'BIO',          'full': 'BIO 國際生技年會',        'period': '2026-06 TBD',      'focus': '授權/BD 交易'},
    {'name': '台灣生技月',    'full': 'BioTaiwan',              'period': '2026-07 TBD',      'focus': '台灣生技'},
]


def get_upcoming_catalysts(code: str, days_ahead: int = 90) -> list[dict]:
    """取得未來 N 天內的催化劑事件"""
    cat_data = CATALYSTS.get(code, {})
    events = cat_data.get('events', [])
    today = datetime.today()
    cutoff = today + timedelta(days=days_ahead)

    upcoming = []
    for ev in events:
        date_str = ev.get('date', '')
        # 嘗試解析具體日期
        parsed_date = _parse_event_date(date_str)
        if parsed_date:
            days_left = (parsed_date - today).days
            if -7 <= days_left <= days_ahead:  # 包含剛過去 7 天內的事件
                upcoming.append({**ev, 'days_left': days_left, 'parsed_date': parsed_date})
        else:
            # 季度/模糊日期，直接加入不過濾
            upcoming.append({**ev, 'days_left': None, 'parsed_date': None})

    upcoming.sort(key=lambda x: x['days_left'] if x['days_left'] is not None else 9999)
    return upcoming


def get_upcoming_conferences(days_ahead: int = 180) -> list[dict]:
    """取得未來 N 天內的重要醫學年會"""
    today = datetime.today()
    result = []
    for conf in MAJOR_CONFERENCES_2026:
        period = conf.get('period', '')
        start_date = _parse_conf_date(period)
        if start_date:
            days_left = (start_date - today).days
            if -3 <= days_left <= days_ahead:
                result.append({**conf, 'days_left': days_left})
    result.sort(key=lambda x: x.get('days_left', 9999))
    return result


def format_catalyst_report(codes: list[str]) -> str:
    lines = ['', '【催化劑日曆】', '']

    # 各股催化劑
    has_any = False
    for code in codes:
        from config import STOCKS
        name = STOCKS.get(code, {}).get('name', code)
        events = get_upcoming_catalysts(code, days_ahead=180)
        if not events:
            lines.append(f'  {name}({code})：尚未填入催化劑事件')
            lines.append(f'           → 請至 config.py 的 CATALYSTS["{code}"]["events"] 填入')
            lines.append(f'           → 資料來源：公司法說會 / 重大訊息 / ClinicalTrials.gov')
            continue
        has_any = True
        lines.append(f'  ▶ {name}({code})')
        for ev in events:
            days = ev.get('days_left')
            if days is not None:
                if days < 0:
                    time_label = f'（{abs(days)} 天前）'
                elif days == 0:
                    time_label = '【今日】'
                elif days <= 30:
                    time_label = f'【⚡ {days} 天後】'
                else:
                    time_label = f'（{days} 天後）'
            else:
                time_label = f'（{ev["date"]}）'

            impact_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(ev.get('impact', ''), '❓')
            dir_icon = {'positive': '📈', 'negative': '📉', 'binary': '⚡'}.get(ev.get('direction', ''), '')
            lines.append(f'    {impact_icon}{dir_icon} {time_label} {ev.get("description", "")}')
            if ev.get('notes'):
                lines.append(f'       備注：{ev["notes"]}')
        lines.append('')

    # 重要醫學年會
    lines.append('  ── 近期重要國際醫學年會 ──')
    confs = get_upcoming_conferences(days_ahead=180)
    if confs:
        for c in confs:
            days = c.get('days_left', 0)
            if days <= 30:
                urgency = f'【⚡ {days}天後】'
            else:
                urgency = f'（{days}天後）'
            lines.append(f'  📅 {urgency} {c["name"]} {c["full"]}  [{c["focus"]}]  {c["period"]}')
    else:
        lines.append('  （近期無醫學年會）')

    return '\n'.join(lines)


def _parse_event_date(date_str: str):
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_conf_date(period: str):
    if not period or 'TBD' in period:
        return None
    part = period.split('/')[0].split(' ')[0]
    for fmt in ('%Y-%m-%d', '%Y-%m'):
        try:
            return datetime.strptime(part, fmt)
        except ValueError:
            continue
    return None
