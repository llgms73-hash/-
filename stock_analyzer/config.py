"""
生技股分析工具 - 設定檔
監控股票：漢康-KY(7827), 康霈(6919), 泰合(6467), 竟天(6917)
⚠️ 注意：7827=漢康-KY、6919=康霈（非原始順序）
"""

# ── 監控股票清單 ──────────────────────────────────────────────
STOCKS = {
    '7827': {'name': '漢康-KY', 'market': 'innovation', 'type': 'biotech'},  # 創新板
    '6919': {'name': '康霈',    'market': 'otc',         'type': 'biotech'},  # 上櫃
    '6467': {'name': '泰合',    'market': 'otc',         'type': 'biotech'},  # 上櫃
    '6917': {'name': '竟天',    'market': 'otc',         'type': 'biotech'},  # 上櫃
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

    # ════════════════════════════════════════════════════════════
    # 7827 漢康-KY（HanchorBio）創新板
    # 核心平台：FBDB（Flexible Bispecific Domain Building-block）
    # 核心藥物：HCB101 — CD47靶向融合蛋白，廣譜抗癌
    # 已完成：中國/特定地區授權給洛康藥業 USD 2.02億（TWD ~65億）
    # ════════════════════════════════════════════════════════════
    '7827': {
        'cash_twd_mn': None,        # 待補：最新季報現金
        'burn_rate_twd_mn': None,   # 待補：每季現金消耗
        'products': [
            {
                'name': 'HCB101-胃癌(2L)',
                'phase': 'Phase2',
                'indication': '二線胃癌',
                'territory': '全球（排除中國/特定地區）',
                'market_usd_bn': 4.5,   # 全球胃癌藥物市場
                'peak_sales_bn': 0.5,   # 保守估算（二線市場+CD47機制）
                'prob_success': 0.28,   # Phase2歷史成功率
                'royalty_rate': 0.12,   # 預期授權金率
                'years_to_mkt': 4,      # 預計2030年前後（Phase2b→3→NDA）
                'discount_rate': 0.15,
                'notes': (
                    'ORR 80%（中劑量組+標準療法），FDA孤兒藥資格，'
                    'Phase2a多國多中心進行中，Phase2b目標2026H2啟動，'
                    '突破性療法申請目標2026Q1'
                ),
            },
            {
                'name': 'HCB101-胃癌(1L)',
                'phase': 'Phase1',
                'indication': '一線胃癌',
                'territory': '全球（排除中國/特定地區）',
                'market_usd_bn': 4.5,
                'peak_sales_bn': 0.8,
                'prob_success': 0.52,
                'royalty_rate': 0.12,
                'years_to_mkt': 6,
                'discount_rate': 0.18,
                'notes': '臨床中，一線空間更大',
            },
            {
                'name': 'HCB101-三陰乳癌(1L)',
                'phase': 'Phase1',
                'indication': '一線三陰性乳癌',
                'territory': '全球（排除中國/特定地區）',
                'market_usd_bn': 6.0,   # TNBC市場規模
                'peak_sales_bn': 0.6,
                'prob_success': 0.52,
                'royalty_rate': 0.12,
                'years_to_mkt': 6,
                'discount_rate': 0.18,
                'notes': '臨床中，TNBC市場成長快',
            },
            {
                'name': 'HCB101-頭頸癌(2L)',
                'phase': 'Phase1',
                'indication': '二線頭頸部癌症',
                'territory': '全球（排除中國/特定地區）',
                'market_usd_bn': 3.0,
                'peak_sales_bn': 0.3,
                'prob_success': 0.52,
                'royalty_rate': 0.12,
                'years_to_mkt': 6,
                'discount_rate': 0.18,
                'notes': '臨床中',
            },
        ],
    },

    # ════════════════════════════════════════════════════════════
    # 6919 康霈生技（Caliway Biopharma）上櫃
    # 核心機制：誘導脂肪細胞凋亡（Apoptosis of adipocytes）
    # 核心藥物：CBL-514 注射劑 — 局部減脂/罕見病
    # 2026最新：SUPREME-01(Ph3) IND通過、SUPREME-02(Ph3) IND通過
    # ════════════════════════════════════════════════════════════
    '6919': {
        'cash_twd_mn': None,        # 待補：最新季報現金
        'burn_rate_twd_mn': None,   # 待補：每季現金消耗
        'products': [
            {
                'name': 'CBL-514 局部減脂(SUPREME-01)',
                'phase': 'Phase3',
                'indication': '腹部皮下脂肪局部減少',
                'territory': '全球',
                'market_usd_bn': 7.0,   # 非侵入性塑身市場（注射類）
                'peak_sales_bn': 0.8,   # 保守估算（first-in-class）
                'prob_success': 0.57,   # Phase3歷史成功率
                'royalty_rate': 0.15,   # 預期授權金率（醫美市場偏高）
                'years_to_mkt': 3,      # 2029年前後NDA
                'discount_rate': 0.12,
                'notes': (
                    'FDA IND 2025年7月通過，多國多中心，全球首創脂肪凋亡機制，'
                    '臨床結果預計2027年，競爭者：Kybella（已核准，頸部；腹部市場空缺）'
                ),
            },
            {
                'name': 'CBL-514 局部減脂(SUPREME-02)',
                'phase': 'Phase3',
                'indication': '腹部皮下脂肪局部減少（第二樞紐）',
                'territory': '全球',
                'market_usd_bn': 7.0,
                'peak_sales_bn': 0.5,
                'prob_success': 0.57,
                'royalty_rate': 0.15,
                'years_to_mkt': 3,
                'discount_rate': 0.12,
                'notes': 'FDA IND 2026年5月18日通過，與SUPREME-01並行，強化數據包',
            },
            {
                'name': 'CBL-514 + GLP-1 體重管理(CBL-0201WR)',
                'phase': 'Phase2',
                'indication': '體重管理（合併tirzepatide）',
                'territory': '全球',
                'market_usd_bn': 80.0,  # 全球肥胖藥物市場（GLP-1浪潮）
                'peak_sales_bn': 1.5,   # 若成功作為GLP-1輔助療法潛力巨大
                'prob_success': 0.28,
                'royalty_rate': 0.12,
                'years_to_mkt': 5,
                'discount_rate': 0.15,
                'notes': (
                    'IND 2025年12月向FDA送件，搭配Eli Lilly tirzepatide，'
                    '若與GLP-1聯用得以核准，市場空間從醫美跳升到肥胖症等級'
                ),
            },
            {
                'name': 'CBL-514 德爾肯氏病（罕病）',
                'phase': 'Phase2',
                'indication': "Dercum's Disease（德爾肯氏病）",
                'territory': '全球',
                'market_usd_bn': 0.5,   # 罕病市場小但定價高
                'peak_sales_bn': 0.2,
                'prob_success': 0.40,   # 罕病FDA審查相對寬鬆
                'royalty_rate': 1.0,    # 直銷（罕病市場自銷較合理）
                'years_to_mkt': 4,
                'discount_rate': 0.12,
                'notes': '孤兒藥資格，無現有標準療法，FDA審查優先（6個月）',
            },
            {
                'name': 'CBL-514 亞太二期(CBL-0206)',
                'phase': 'Phase2',
                'indication': '腹部皮下脂肪（亞洲族群）',
                'territory': '亞太',
                'market_usd_bn': 2.0,
                'peak_sales_bn': 0.2,
                'prob_success': 0.28,
                'royalty_rate': 0.15,
                'years_to_mkt': 4,
                'discount_rate': 0.15,
                'notes': '澳洲已核准、台灣TFDA已通過IND，補充亞洲族群數據',
            },
        ],
    },

    # ════════════════════════════════════════════════════════════
    # 6467 泰合生技藥品（Taho Pharmaceuticals）上櫃
    # 核心策略：505(b)(2) 新劑型新藥（非NCE）→ 風險低，速度快
    # 核心藥物：TAH3311 — Apixaban口溶膜（吞嚥困難病患抗血栓）
    # 最新：NDA已送件FDA，收到RTF（格式問題，非臨床問題），2026Q3計劃重新送件
    # ════════════════════════════════════════════════════════════
    '6467': {
        'cash_twd_mn': None,        # 待補：最新季報現金（已知2023年虧1.2億、2024年虧1.67億）
        'burn_rate_twd_mn': None,   # 待補：每季現金消耗
        'products': [
            {
                'name': 'TAH3311 抗血栓口溶膜（美國NDA）',
                'phase': 'NDA/BLA',  # NDA已送件但收到RTF，視為NDA階段
                'indication': '抗血栓（吞嚥困難病患用Apixaban口溶膜劑型）',
                'territory': '美國',
                'market_usd_bn': 8.0,   # 美國口服抗凝藥市場（Apixaban全球年銷約100億）
                'peak_sales_bn': 0.3,   # 吞嚥困難族群子市場（保守）
                'prob_success': 0.75,   # 505(b)(2)歷史核准率較高（臨床數據已OK，純格式問題）
                'royalty_rate': 1.0,    # 計劃直銷或授權（若授權調降為0.15-0.20）
                'years_to_mkt': 2,      # RTF修正→重送→FDA審查約12個月→2027-2028
                'discount_rate': 0.12,
                'notes': (
                    '全球首創Apixaban口溶膜；FDA RTF原因：穩定性資料不足、'
                    '包材DMF授權信缺件（非臨床問題）；2026Q3計劃重新向美/歐送件；'
                    '15M新中風患者/年，50%有吞嚥困難；全球首創→定價議價空間大'
                ),
            },
            {
                'name': 'TAH3311 抗血栓口溶膜（歐洲NDA）',
                'phase': 'Phase3',  # 歐洲尚未送件，預計2026Q3
                'indication': '抗血栓（吞嚥困難病患用Apixaban口溶膜劑型）',
                'territory': '歐洲',
                'market_usd_bn': 6.0,
                'peak_sales_bn': 0.2,
                'prob_success': 0.65,
                'royalty_rate': 0.18,   # 歐洲通常授權出去
                'years_to_mkt': 3,
                'discount_rate': 0.12,
                'notes': '計劃2026Q3同步向歐洲EMA送件',
            },
            {
                'name': 'TAH4411 化療止吐口溶膜（日本已核准）',
                'phase': 'Approved',
                'indication': '化療引起的噁心嘔吐（CINV）',
                'territory': '日本',
                'market_usd_bn': 1.5,
                'peak_sales_bn': 0.08,  # 日本市場份額
                'prob_success': 1.00,
                'royalty_rate': 0.15,
                'years_to_mkt': 0,
                'discount_rate': 0.10,
                'notes': '已獲日本厚生勞動省核准，商業化推進中',
            },
        ],
    },

    # ════════════════════════════════════════════════════════════
    # 6917 竟天生技（Andros Biotech）上櫃
    # 核心策略：罕見疼痛適應症局部注射新藥
    # APC201：骨關節炎局部疼痛（Phase2完成收案，2026Q1結果）
    # APC101：帶狀皰疹後神經痛（Phase2台灣進行中）
    # ════════════════════════════════════════════════════════════
    '6917': {
        'cash_twd_mn': None,        # 待補：最新季報現金（曾辦2.6億現增）
        'burn_rate_twd_mn': None,   # 待補：每季現金消耗
        'products': [
            {
                'name': 'APC201 骨關節炎局部疼痛',
                'phase': 'Phase2',
                'indication': '膝蓋骨關節炎引起之局部疼痛',
                'territory': '全球',
                'market_usd_bn': 9.9,   # 2024全球OA治療市場（Precedence Research）
                'peak_sales_bn': 0.15,  # 局部注射細分市場，保守估算
                'prob_success': 0.28,   # Phase2成功率
                'royalty_rate': 0.12,
                'years_to_mkt': 5,      # Phase2→Phase3→NDA
                'discount_rate': 0.15,
                'notes': (
                    'Phase1/2a澳洲完成，主次要療效指標均正向；'
                    'Phase2（60名患者）完成收案，2026Q1結果（已到期，應已有初步數據）；'
                    '市場CAGR 9.4%，2034年預估243億美元；'
                    'APC201若成功將推全球多中心Phase3+授權談判+IPO加速'
                ),
            },
            {
                'name': 'APC101 帶狀皰疹後神經痛',
                'phase': 'Phase2',
                'indication': '頭頸部帶狀皰疹後神經痛（PHN）',
                'territory': '全球',
                'market_usd_bn': 3.5,   # 神經痛藥物市場
                'peak_sales_bn': 0.1,
                'prob_success': 0.28,
                'royalty_rate': 0.12,
                'years_to_mkt': 6,
                'discount_rate': 0.15,
                'notes': (
                    '台灣Phase2進行中，2024年9月完成首例收案；'
                    'PHN為帶狀皰疹最常見且痛苦的後遺症，現有藥物效果有限'
                ),
            },
        ],
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
