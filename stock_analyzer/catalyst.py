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

    # ── 7827 漢康-KY ─────────────────────────────────────────
    '7827': {
        'company_basics': {
            'shares_mn': None,
            'listing_date': '2026-06-29',   # 創新板掛牌日（上市價120元）
            'ir_page': 'https://geneonline.news/hanchorbio-fbdb-hcb101/',
            'clinical_trials_ids': [],
        },
        'events': [
            {
                'date': '2026-Q1',
                'event_type': 'milestone',
                'product': 'HCB101',
                'description': '向FDA申請HCB101胃癌突破性療法認定（BT Designation）',
                'impact': 'high',
                'direction': 'positive',
                'notes': '若獲BT認定，FDA提供密切指導，加速審查，對股價+30~60%',
            },
            {
                'date': '2026-H2',
                'event_type': 'milestone',
                'product': 'HCB101',
                'description': 'Phase 2b（二線胃癌）啟動',
                'impact': 'high',
                'direction': 'positive',
                'notes': 'Phase2b是獲得授權前最關鍵一步',
            },
            {
                'date': '2026',
                'event_type': 'bd_deal',
                'product': 'HCB101',
                'description': '全球/區域授權交易（非中國地區）',
                'impact': 'high',
                'direction': 'positive',
                'notes': (
                    '公司目標年內完成，首付款+里程碑金，參考洛康案USD2.02億；'
                    '成功授權可能驅動股價翻倍，是最大催化劑'
                ),
            },
            {
                'date': '2026-Q4',
                'event_type': 'trial_result',
                'product': 'HCB101',
                'description': 'Phase 2a 二線胃癌數據更新公布',
                'impact': 'high',
                'direction': 'binary',
                'notes': '數據公布通常在醫學年會（ESMO/ASCO/AACR），正向則催化授權談判',
            },
        ],
    },

    # ── 6919 康霈生技 ────────────────────────────────────────
    '6919': {
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': 'https://www.caliwaybiopharma.com/en/investor/',
            'clinical_trials_ids': ['CBL-0301', 'CBL-0302'],
        },
        'events': [
            {
                'date': '2026-06-04',
                'event_type': 'milestone',
                'product': 'CBL-514',
                'description': 'CBL-0303（Phase3b長期追蹤）IND向FDA送件',
                'impact': 'medium',
                'direction': 'positive',
                'notes': '補充長期安全性資料，為NDA鋪路',
            },
            {
                'date': '2026-H2',
                'event_type': 'milestone',
                'product': 'CBL-514',
                'description': 'SUPREME-01 & SUPREME-02 Phase3收案速度更新',
                'impact': 'medium',
                'direction': 'positive',
                'notes': '收案速度決定2027年能否如期有頂線數據',
            },
            {
                'date': '2026-H2',
                'event_type': 'milestone',
                'product': 'CBL-514',
                'description': 'CBL-0304（中國Phase3）IND送件計劃',
                'impact': 'medium',
                'direction': 'positive',
                'notes': '中國市場授權或自行開發',
            },
            {
                'date': '2027-H1',
                'event_type': 'trial_result',
                'product': 'CBL-514',
                'description': 'SUPREME-01 頂線數據預期公布',
                'impact': 'high',
                'direction': 'binary',
                'notes': (
                    '最重要催化劑；成功則估值重評（NDA申請+授權談判）；'
                    '失敗則股價腰斬風險；現在買要能承擔等到2027年的時間成本'
                ),
            },
            {
                'date': '2026',
                'event_type': 'trial_result',
                'product': 'CBL-514+GLP-1',
                'description': 'CBL-0201WR（合併tirzepatide）Phase2 IND通過後啟動',
                'impact': 'high',
                'direction': 'positive',
                'notes': '若切入GLP-1輔助療法市場，市場空間從數十億跳升至數百億美元',
            },
        ],
    },

    # ── 6467 泰合生技 ────────────────────────────────────────
    '6467': {
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': '',
            'clinical_trials_ids': [],
        },
        'events': [
            {
                'date': '2025-12-12',
                'event_type': 'other',
                'product': 'TAH3311',
                'description': '美國FDA發出RTF（查驗文件退件）',
                'impact': 'high',
                'direction': 'negative',
                'notes': (
                    '⚠️ 原因：穩定性資料不足、包材DMF授權信缺件（非臨床問題）；'
                    '臨床數據FDA無異議；RTF ≠ 臨床失敗，但延誤12-18個月'
                ),
            },
            {
                'date': '2026-Q3',
                'event_type': 'milestone',
                'product': 'TAH3311',
                'description': '重新向美國FDA及歐洲EMA送件NDA',
                'impact': 'high',
                'direction': 'positive',
                'notes': '若順利送件且FDA接受，PDUFA日期約2027Q3-Q4',
            },
            {
                'date': '2027-Q3',
                'event_type': 'fda_action',
                'product': 'TAH3311',
                'description': '美國FDA PDUFA日期（預估）',
                'impact': 'high',
                'direction': 'binary',
                'notes': '核准則轉上市+開始商業化；拒絕則需補充更多數據',
            },
            {
                'date': '2026',
                'event_type': 'bd_deal',
                'product': 'TAH3311',
                'description': '年底前完成授權目標',
                'impact': 'high',
                'direction': 'positive',
                'notes': '公司計劃授權後再IPO轉上市，授權金是股價最大催化劑',
            },
        ],
    },

    # ── 6917 竟天生技 ────────────────────────────────────────
    '6917': {
        'company_basics': {
            'shares_mn': None,
            'listing_date': None,
            'ir_page': '',
            'clinical_trials_ids': [],
        },
        'events': [
            {
                'date': '2026-Q1',
                'event_type': 'trial_result',
                'product': 'APC201',
                'description': 'APC201 Phase2 初步數據結果公布（已到期）',
                'impact': 'high',
                'direction': 'binary',
                'notes': (
                    '⚠️ 預計2026Q1應已有數據，請查最新重大訊息確認；'
                    'Phase1/2a結果已正向（療效+安全性）；'
                    'Phase2正向→啟動全球Phase3+國際授權談判'
                ),
            },
            {
                'date': '2026',
                'event_type': 'bd_deal',
                'product': 'APC201',
                'description': 'APC201全球市場授權洽談',
                'impact': 'high',
                'direction': 'positive',
                'notes': (
                    '公司計劃Phase2數據後啟動授權；骨關節炎市場$99億(2024)→$243億(2034)；'
                    '授權金是最大股價催化劑'
                ),
            },
            {
                'date': '2026',
                'event_type': 'milestone',
                'product': 'APC201',
                'description': 'IPO加速計劃（轉上市）',
                'impact': 'medium',
                'direction': 'positive',
                'notes': '授權+IPO雙引擎，若授權成功股本稀釋風險降低',
            },
            {
                'date': '2026-2027',
                'event_type': 'trial_result',
                'product': 'APC101',
                'description': 'APC101（帶狀皰疹後神經痛）台灣Phase2 期中分析',
                'impact': 'medium',
                'direction': 'binary',
                'notes': '2024年9月首例收案，預估2026-2027有期中或最終數據',
            },
        ],
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
