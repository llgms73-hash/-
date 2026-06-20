"""
估值模組
- 生技股（無營收）：Pipeline NPV 法 + 現金跑道
- 一般股（有營收）：P/E、EV/EBITDA、DCF 框架
"""

from config import PIPELINE, PHASE_SUCCESS_RATES, DISCOUNT_RATES, ALERT_CONFIG


# ── 生技股估值 ────────────────────────────────────────────────

def calc_product_npv(product: dict) -> dict:
    """
    計算單一 Pipeline 產品的 risk-adjusted NPV（rNPV）

    公式：
        rNPV = peak_sales × royalty_rate × revenue_multiple
               × prob_success × 1/(1+discount_rate)^years_to_mkt
    """
    phase = product.get('phase', 'Phase1')
    prob  = product.get('prob_success',
                        PHASE_SUCCESS_RATES.get(phase, 0.10))
    disc  = product.get('discount_rate',
                        DISCOUNT_RATES.get(phase, 0.15))
    peak  = product.get('peak_sales_bn', 0.0)      # 十億美元
    royal = product.get('royalty_rate', 1.0)
    years = product.get('years_to_mkt', 5)

    # 製藥業授權案通常以峰值銷售 × 3~5 倍估企業價值（EV）
    # 這裡直接用峰值銷售的折現現值作保守估算
    revenue_multiple = 4.0  # 保守起見用 4x
    pv_peak = peak * royal * revenue_multiple / ((1 + disc) ** years)
    rnpv = pv_peak * prob

    return {
        'name':         product.get('name', '未命名'),
        'phase':        phase,
        'indication':   product.get('indication', ''),
        'territory':    product.get('territory', '全球'),
        'prob_success': prob,
        'peak_sales_bn': peak,
        'royalty_rate': royal,
        'years_to_mkt': years,
        'pv_peak_bn':   round(pv_peak, 4),
        'rnpv_bn':      round(rnpv, 4),
        'rnpv_twd_mn':  round(rnpv * 30_000, 0),  # 以 1 USD = 30 TWD 估算
    }


def calc_biotech_valuation(code: str, name: str,
                            share_price: float = 0,
                            shares_outstanding_mn: float = 0) -> dict:
    """
    生技股估值：Pipeline rNPV + 現金
    """
    info = PIPELINE.get(code, {})
    products = info.get('products', [])
    cash_mn   = info.get('cash_twd_mn')         # 百萬台幣
    burn_mn   = info.get('burn_rate_twd_mn')    # 每季，百萬台幣

    if not products:
        return {
            'code': code,
            'name': name,
            'status': '⚠️ Pipeline 資料未填入，請至 config.py 依 IR 簡報更新',
            'notes': [
                '需填入：產品代號、臨床階段、適應症、授權地區、峰值銷售估算',
                '資料來源：公司法說會簡報、重大訊息、ClinicalTrials.gov',
            ],
        }

    product_npvs = [calc_product_npv(p) for p in products]
    total_pipeline_rnpv_bn = sum(p['rnpv_bn'] for p in product_npvs)
    total_pipeline_twd_mn  = sum(p['rnpv_twd_mn'] for p in product_npvs)

    # 加上現金
    cash_value_mn = cash_mn or 0
    total_value_mn = total_pipeline_twd_mn + cash_value_mn

    # 現金跑道
    cash_runway = None
    runway_alert = None
    if cash_mn and burn_mn and burn_mn > 0:
        cash_runway = round(cash_mn / burn_mn * 3, 1)  # burn_mn 是每季，轉月份
        if cash_runway < ALERT_CONFIG['cash_runway_months']:
            runway_alert = f'🔴 現金跑道僅 {cash_runway} 個月，稀釋風險高！'

    # 合理股價估算（每股 NAV）
    nav_per_share = None
    premium_discount = None
    if shares_outstanding_mn and shares_outstanding_mn > 0:
        nav_per_share = round(total_value_mn / shares_outstanding_mn, 2)
        if share_price and nav_per_share:
            prem = (share_price - nav_per_share) / nav_per_share * 100
            premium_discount = round(prem, 1)

    return {
        'code': code,
        'name': name,
        'pipeline_products': product_npvs,
        'total_pipeline_rnpv_usd_bn': round(total_pipeline_rnpv_bn, 4),
        'total_pipeline_twd_mn': round(total_pipeline_twd_mn, 0),
        'cash_twd_mn': cash_mn,
        'total_value_twd_mn': round(total_value_mn, 0),
        'cash_runway_months': cash_runway,
        'runway_alert': runway_alert,
        'nav_per_share_twd': nav_per_share,
        'current_price': share_price,
        'premium_vs_nav_pct': premium_discount,
        'valuation_note': (
            '⚠️ 以上為保守 rNPV 估算（峰值銷售×4倍×折現×成功率），'
            '實際市場可能給予更高溢價（pipeline 期待值）。'
            '股價高於 NAV 屬正常，差距越大代表市場樂觀預期越強，也代表下跌空間更大。'
        ),
    }


# ── 一般股票估值（有營收）────────────────────────────────────

def calc_general_valuation(
    code: str,
    name: str,
    # 基本面數據（需從財報或 API 取得）
    share_price: float = 0,
    shares_mn: float = 0,
    eps_ttm: float = 0,          # 近四季 EPS
    book_value_per_share: float = 0,  # 每股淨值
    ebitda_mn: float = 0,        # 近四季 EBITDA（百萬台幣）
    net_debt_mn: float = 0,      # 淨負債（百萬台幣）
    revenue_ttm_mn: float = 0,   # 近四季營收
    net_income_ttm_mn: float = 0,
    sector: str = '電子',
) -> dict:
    """
    一般股票估值（適用有營收、有獲利的公司）
    """
    mkt_cap_mn = share_price * shares_mn if share_price and shares_mn else 0

    pe   = round(share_price / eps_ttm, 1)        if eps_ttm > 0 else None
    pb   = round(share_price / book_value_per_share, 2) if book_value_per_share > 0 else None
    ev_mn = mkt_cap_mn + net_debt_mn
    ev_ebitda = round(ev_mn / ebitda_mn, 1)       if ebitda_mn > 0 else None
    ps   = round(mkt_cap_mn / revenue_ttm_mn, 2)  if revenue_ttm_mn > 0 else None
    net_margin = round(net_income_ttm_mn / revenue_ttm_mn * 100, 1) \
                 if revenue_ttm_mn > 0 else None

    # 業界本益比參考（台灣股市常見區間）
    sector_pe_range = {
        '電子':    (15, 25),
        '半導體':  (20, 40),
        '生技醫療': (30, 80),
        '傳產':    (10, 20),
        '金融':    (10, 18),
        '電信':    (12, 20),
    }
    ref_pe = sector_pe_range.get(sector, (15, 25))

    # 合理股價區間（用 P/E 法）
    fair_low  = eps_ttm * ref_pe[0] if eps_ttm else None
    fair_high = eps_ttm * ref_pe[1] if eps_ttm else None

    signals = []
    if pe and ref_pe:
        if pe > ref_pe[1] * 1.5:
            signals.append(f'⚠️ 本益比 {pe}x 遠高於同業區間 {ref_pe[0]}-{ref_pe[1]}x')
        elif pe < ref_pe[0] * 0.7:
            signals.append(f'✅ 本益比 {pe}x 低於同業，可能被低估')
    if pb and pb < 1.0:
        signals.append(f'✅ P/B {pb}x < 1，股價低於淨資產（注意是否有隱藏損失）')
    if pb and pb > 5.0:
        signals.append(f'⚠️ P/B {pb}x 偏高，須確認 ROE 是否支撐')

    return {
        'code': code,
        'name': name,
        'valuation_type': '一般股票（有營收）',
        'market_cap_mn': round(mkt_cap_mn, 0),
        'metrics': {
            'P/E (本益比)': pe,
            'P/B (股價淨值比)': pb,
            'EV/EBITDA': ev_ebitda,
            'P/S (股價營收比)': ps,
            '淨利率 %': net_margin,
        },
        'fair_value_range_twd': {
            '低估區': fair_low,
            '合理上限': fair_high,
        },
        'sector_pe_reference': f'{sector} 同業區間 {ref_pe[0]}-{ref_pe[1]}x',
        'signals': signals,
        'note': '以上使用 TTM（近四季）數據，需確認數字來自最新財報',
    }
