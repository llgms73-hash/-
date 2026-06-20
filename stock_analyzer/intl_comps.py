"""
國際市場比較基準模組
協助評估台灣生技股的國際競爭地位與授權價值

資料來源：
- EvaluatePharma 年報（免費摘要）
- BioPharma Catalyst 公開統計
- FDA 審批歷史資料庫
- 各大生技 BD 交易公開公告
"""

# ── 各適應症全球市場規模參考（十億美元，2024-2025 數據）────────
# 來源：EvaluatePharma, GlobalData, IQVIA 公開報告摘要
GLOBAL_MARKET_SIZE = {
    # 腫瘤科
    '肺癌 NSCLC':         {'size_usd_bn': 28.0,  'cagr_pct': 12, 'key_players': 'AstraZeneca, Roche, BMS'},
    '肺癌 SCLC':          {'size_usd_bn': 4.5,   'cagr_pct': 8,  'key_players': 'AstraZeneca, BMS'},
    '大腸直腸癌':          {'size_usd_bn': 12.0,  'cagr_pct': 7,  'key_players': 'Roche, Regeneron'},
    '乳癌':               {'size_usd_bn': 32.0,  'cagr_pct': 10, 'key_players': 'Roche, AstraZeneca, Pfizer'},
    '胰臟癌':             {'size_usd_bn': 3.8,   'cagr_pct': 9,  'key_players': 'Ipsen, Jazz'},
    '膀胱癌':             {'size_usd_bn': 5.2,   'cagr_pct': 11, 'key_players': 'BMS, Roche'},
    '肝癌 HCC':           {'size_usd_bn': 5.6,   'cagr_pct': 9,  'key_players': 'Bayer, BMS, Roche'},
    '血液腫瘤 AML':        {'size_usd_bn': 4.8,   'cagr_pct': 8,  'key_players': 'AbbVie, Jazz, Astellas'},
    '多發性骨髓瘤':        {'size_usd_bn': 28.0,  'cagr_pct': 13, 'key_players': 'J&J, BMS, Sanofi'},
    # 代謝/內分泌
    '肥胖症':             {'size_usd_bn': 80.0,  'cagr_pct': 35, 'key_players': 'Novo Nordisk, Eli Lilly'},
    '第二型糖尿病':        {'size_usd_bn': 70.0,  'cagr_pct': 5,  'key_players': 'Novo Nordisk, Eli Lilly, AZ'},
    'NASH/MASH':         {'size_usd_bn': 25.0,  'cagr_pct': 40, 'key_players': 'Madrigal, Novo Nordisk'},
    # 免疫/發炎
    '類風濕關節炎':        {'size_usd_bn': 28.0,  'cagr_pct': 4,  'key_players': 'AbbVie, J&J, Pfizer'},
    '異位性皮膚炎':        {'size_usd_bn': 14.0,  'cagr_pct': 18, 'key_players': 'Sanofi/Regen, Pfizer, AbbVie'},
    '乾癬':               {'size_usd_bn': 23.0,  'cagr_pct': 8,  'key_players': 'AbbVie, J&J, Novartis'},
    'IBD 克隆氏症':        {'size_usd_bn': 18.0,  'cagr_pct': 6,  'key_players': 'AbbVie, J&J, Takeda'},
    # 神經科學
    '阿茲海默症':          {'size_usd_bn': 12.0,  'cagr_pct': 45, 'key_players': 'Biogen/Eisai, Eli Lilly'},
    '帕金森氏症':          {'size_usd_bn': 5.2,   'cagr_pct': 8,  'key_players': 'AbbVie, Biogen'},
    '罕見神經疾病':        {'size_usd_bn': 8.5,   'cagr_pct': 12, 'key_players': 'Biogen, Sarepta'},
    # 感染症
    'HIV':               {'size_usd_bn': 30.0,  'cagr_pct': 3,  'key_players': 'Gilead, ViiV/GSK'},
    'HBV 慢性B型肝炎':    {'size_usd_bn': 3.8,   'cagr_pct': 6,  'key_players': 'Gilead, Roche'},
    # 眼科
    '濕式黃斑部病變 AMD': {'size_usd_bn': 14.0,  'cagr_pct': 7,  'key_players': 'Regeneron, Novartis, Roche'},
    # 罕見疾病
    '罕見疾病（一般）':    {'size_usd_bn': 3.0,   'cagr_pct': 12, 'key_players': '視疾病而異'},
}

# ── 授權交易基準（按臨床階段，2019-2025 公開交易統計）──────────
# 來源：BioPharma Catalyst, Citeline, EvaluatePharma 公開統計
# 注意：台灣公司因市場規模較小，通常拿到的條件低於全球平均 20-40%
BD_DEAL_BENCHMARKS = {
    'Pre-IND': {
        'upfront_usd_mn':  {'min': 1,   'median': 5,    'max': 30},
        'total_usd_mn':    {'min': 30,  'median': 100,  'max': 500},
        'royalty_pct':     {'min': 5,   'median': 8,    'max': 12},
        'note': '概念期授權，風險最高，upfront 通常很少',
    },
    'Phase1': {
        'upfront_usd_mn':  {'min': 5,   'median': 20,   'max': 100},
        'total_usd_mn':    {'min': 50,  'median': 200,  'max': 1000},
        'royalty_pct':     {'min': 6,   'median': 10,   'max': 15},
        'note': '有初步安全性數據，授權條件開始改善',
    },
    'Phase2': {
        'upfront_usd_mn':  {'min': 20,  'median': 80,   'max': 500},
        'total_usd_mn':    {'min': 200, 'median': 500,  'max': 3000},
        'royalty_pct':     {'min': 8,   'median': 12,   'max': 20},
        'note': '有初步療效數據，大藥廠最常出手的階段',
    },
    'Phase3': {
        'upfront_usd_mn':  {'min': 100, 'median': 300,  'max': 2000},
        'total_usd_mn':    {'min': 500, 'median': 1500, 'max': 10000},
        'royalty_pct':     {'min': 12,  'median': 18,   'max': 25},
        'note': '風險大幅降低，upfront 通常很高，但談判空間較小',
    },
    'Approved': {
        'upfront_usd_mn':  {'min': 200, 'median': 800,  'max': 5000},
        'total_usd_mn':    {'min': 800, 'median': 3000, 'max': 20000},
        'royalty_pct':     {'min': 15,  'median': 22,   'max': 30},
        'note': '已核准產品授權，通常為地區性合作',
    },
}

# ── 歷史臨床成功率（FDA 2006-2015, BIO/Biomedtracker 2011-2020）─
PHASE_TRANSITION_RATES = {
    'Phase1 → Phase2': 0.52,
    'Phase2 → Phase3': 0.28,
    'Phase3 → NDA':    0.57,
    'NDA → Approval':  0.85,
    # 累計從 Phase1 到上市
    'Phase1 → Approval': 0.52 * 0.28 * 0.57 * 0.85,  # ≈ 7%
    # 按適應症（腫瘤vs其他）
    '腫瘤 Phase2 → Phase3': 0.25,
    '非腫瘤 Phase2 → Phase3': 0.32,
}

# ── 台灣生技股國際授權案例（公開資訊，近年重要案例）──────────────
# 讓你了解「台灣公司能拿到什麼條件」的現實參考
TAIWAN_BIOTECH_BD_CASES = [
    {
        'company': '中裕新藥',
        'year': 2022,
        'product': 'leronlimab（HIV）',
        'partner': 'CytoDyn',
        'upfront_usd_mn': None,
        'total_usd_mn': None,
        'note': '台灣公司取得亞太授權',
    },
    {
        'company': '太景生技',
        'year': 2019,
        'product': 'Nemonoxacin',
        'partner': '印度 Sun Pharma',
        'upfront_usd_mn': None,
        'total_usd_mn': None,
        'note': '亞洲地區授權，小額里程碑',
    },
    {
        'company': '台灣醣聯',
        'year': 2022,
        'product': 'GalNAc-siRNA 平台',
        'partner': 'OliX Pharma',
        'upfront_usd_mn': None,
        'total_usd_mn': None,
        'note': '技術授權',
    },
    # 注意：多數台灣 BD 案條款未完整揭露，以上為公開揭露部分
]


def get_market_info(indication: str) -> dict | None:
    """查詢適應症的全球市場規模資訊"""
    for key, val in GLOBAL_MARKET_SIZE.items():
        if indication in key or key in indication:
            return {'indication': key, **val}
    return None


def get_bd_benchmark(phase: str) -> dict:
    """取得該臨床階段的授權交易基準數據"""
    return BD_DEAL_BENCHMARKS.get(phase, BD_DEAL_BENCHMARKS.get('Phase2'))


def format_intl_analysis(code: str, name: str, pipeline_products: list) -> str:
    """輸出國際市場比較分析"""
    if not pipeline_products:
        return (
            f'\n  【{name}({code}) 國際市場分析】\n'
            f'  ⚠️ 請先在 config.py 填入 Pipeline 資料後，此模組才能運作\n'
        )

    lines = [f'\n  【{name}({code}) 國際市場比較分析】', '']

    for prod in pipeline_products:
        phase     = prod.get('phase', 'Phase1')
        indic     = prod.get('indication', '未填寫')
        territory = prod.get('territory', '全球')
        royal     = prod.get('royalty_rate', 0)
        peak      = prod.get('peak_sales_bn', 0)

        lines.append(f'  產品：{prod.get("name", "")}  |  {phase}  |  {indic}  |  地區：{territory}')

        # 市場規模
        mkt = get_market_info(indic)
        if mkt:
            lines.append(f'    全球市場：USD {mkt["size_usd_bn"]:.0f} 億  '
                         f'CAGR {mkt["cagr_pct"]}%/年  '
                         f'主要競爭者：{mkt["key_players"]}')
        else:
            lines.append(f'    全球市場：請參考 EvaluatePharma / GlobalData 報告（{indic}）')

        # 授權交易基準
        bench = get_bd_benchmark(phase)
        if bench:
            lines.append(f'    同階段授權基準（{phase}）：')
            lines.append(f'      首付款 USD {bench["upfront_usd_mn"]["min"]}M'
                         f'～{bench["upfront_usd_mn"]["max"]}M'
                         f'  中位數 {bench["upfront_usd_mn"]["median"]}M')
            lines.append(f'      總金額 USD {bench["total_usd_mn"]["median"]}M'
                         f'  ｜  權利金 {bench["royalty_pct"]["min"]}'
                         f'～{bench["royalty_pct"]["max"]}%')

            # 比較公司自填的數字
            if royal > 0:
                bench_mid = bench['royalty_pct']['median'] / 100
                if royal > bench_mid * 1.3:
                    lines.append(f'      ✅ 公司設定權利金率 {royal*100:.0f}% > 市場中位數，估值偏樂觀')
                elif royal < bench_mid * 0.7:
                    lines.append(f'      ✅ 公司設定權利金率 {royal*100:.0f}% < 市場中位數，估值偏保守')
                else:
                    lines.append(f'      ✅ 公司設定權利金率 {royal*100:.0f}% 符合市場合理範圍')

            lines.append(f'      備注：{bench["note"]}')

        # 台灣公司通常折扣
        lines.append(f'    ⚠️ 注意：台灣公司取得的授權條件通常低於全球中位數 20-40%')
        lines.append('')

    # 成功率提醒
    lines.append('  ── 臨床成功率現實提醒 ──')
    lines.append(f'  Phase1 → 最終上市累計成功率：≈ {PHASE_TRANSITION_RATES["Phase1 → Approval"]*100:.0f}%')
    lines.append(f'  Phase2 → Phase3 推進率：      ≈ {PHASE_TRANSITION_RATES["Phase2 → Phase3"]*100:.0f}%')
    lines.append(f'  腫瘤適應症 Phase2 推進率更低：  ≈ {PHASE_TRANSITION_RATES["腫瘤 Phase2 → Phase3"]*100:.0f}%')
    lines.append('')
    lines.append('  ── 近期台灣生技 BD 案參考 ──')
    for case in TAIWAN_BIOTECH_BD_CASES:
        lines.append(f'  {case["year"]} {case["company"]} × {case["partner"]}：{case["note"]}')

    return '\n'.join(lines)
