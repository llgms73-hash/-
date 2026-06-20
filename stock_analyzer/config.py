"""
生技股分析工具 - 設定檔
監控股票：康霈(7827), 漢康-KY(6919), 泰合(6467), 竟天(6917)
"""

# ── 監控股票清單 ──────────────────────────────────────────────
STOCKS = {
    '7827': {'name': '康霈',    'market': 'otc',  'type': 'biotech'},
    '6919': {'name': '漢康-KY', 'market': 'otc',  'type': 'biotech'},
    '6467': {'name': '泰合',    'market': 'otc',  'type': 'biotech'},
    '6917': {'name': '竟天',    'market': 'otc',  'type': 'biotech'},
}

# ── 生技 Pipeline 資料（需依公司 IR 官網手動維護）──────────────
# 格式：
#   phase        : 'Phase1' / 'Phase2' / 'Phase3' / 'Approved' / 'Pre-IND'
#   indication   : 適應症（e.g. '第二型糖尿病'）
#   territory    : 授權地區（e.g. '全球' / '中國' / '美國+歐洲'）
#   market_usd_bn: 目標市場全球規模（十億美元）
#   peak_sales_bn: 估算峰值銷售額（十億美元，含市占率後）
#   prob_success : 從當前 Phase 到上市的歷史成功率（0~1）
#   royalty_rate : 若為授權案，預計權利金率（0~1）；自銷則填 1.0
#   years_to_mkt : 距上市預計年數
#   discount_rate: 折現率（生技標準 0.12~0.20）
# ─────────────────────────────────────────────────────────────
# ⚠️ 以下資料需由使用者依最新 IR 簡報/法說會更新，勿依賴預設值做投資決策

PIPELINE = {
    '7827': {  # 康霈
        'cash_twd_mn': None,         # 最新季報現金（百萬台幣），填入後自動計算跑道
        'burn_rate_twd_mn': None,    # 每季現金消耗（百萬台幣）
        'products': [
            # 範例格式（請依 IR 資料填寫）：
            # {
            #     'name': '產品代號',
            #     'phase': 'Phase2',
            #     'indication': '適應症',
            #     'territory': '全球',
            #     'market_usd_bn': 5.0,
            #     'peak_sales_bn': 0.3,
            #     'prob_success': 0.30,
            #     'royalty_rate': 0.10,
            #     'years_to_mkt': 4,
            #     'discount_rate': 0.15,
            # },
        ],
    },
    '6919': {  # 漢康-KY
        'cash_twd_mn': None,
        'burn_rate_twd_mn': None,
        'products': [],
    },
    '6467': {  # 泰合
        'cash_twd_mn': None,
        'burn_rate_twd_mn': None,
        'products': [],
    },
    '6917': {  # 竟天
        'cash_twd_mn': None,
        'burn_rate_twd_mn': None,
        'products': [],
    },
}

# ── 一般股票（有營收）估值參數（未來擴充用）────────────────────
GENERAL_STOCKS = {
    # 'XXXX': {'name': '公司名', 'type': 'general', 'sector': '電子'},
}

# ── 示警門檻設定 ──────────────────────────────────────────────
ALERT_CONFIG = {
    'institutional_sell_days': 3,      # 三大法人連續賣超幾天 → 警示
    'foreign_sell_days': 3,            # 外資單獨連續賣超幾天 → 警示
    'margin_increase_price_drop': True, # 融資增 + 股價跌 → 危險信號
    'margin_increase_pct': 3.0,        # 融資餘額單日增幅 %
    'short_ratio_warning': 15.0,       # 券資比 > 15% → 注意
    'cash_runway_months': 12,          # 現金跑道 < 12 個月 → 警示
    'price_drop_from_high_pct': 20.0,  # 從近期高點跌幅 > 20% → 警示
    'volume_spike_ratio': 3.0,         # 成交量是 20 日均量的 N 倍 → 注意
}

# ── 生技 Phase 成功率（業界標準，FDA 2006-2015 統計）──────────
PHASE_SUCCESS_RATES = {
    'Pre-IND':  0.07,
    'Phase1':   0.52,
    'Phase2':   0.28,
    'Phase3':   0.57,
    'NDA/BLA':  0.85,
    'Approved': 1.00,
}

# ── 折現率建議範圍 ────────────────────────────────────────────
DISCOUNT_RATES = {
    'Pre-IND': 0.20,
    'Phase1':  0.18,
    'Phase2':  0.15,
    'Phase3':  0.12,
    'Approved': 0.10,
}

# ── HTTP 請求設定 ─────────────────────────────────────────────
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

REQUEST_TIMEOUT = 15   # 秒
RETRY_TIMES = 3
RETRY_DELAY = 2        # 秒
