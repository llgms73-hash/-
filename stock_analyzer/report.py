"""
報告輸出模組
格式化顯示分析結果
"""

from datetime import datetime


DIVIDER = '=' * 70
SUBDIV  = '-' * 50


def _pct_bar(pct: float, width: int = 20) -> str:
    """簡易百分比視覺條"""
    filled = int(min(abs(pct), 100) / 100 * width)
    bar = '█' * filled + '░' * (width - filled)
    return f'[{bar}] {pct:+.1f}%'


def print_header(title: str):
    print(f'\n{DIVIDER}')
    print(f'  {title}')
    print(f'  產生時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(DIVIDER)


def print_price_block(price: dict, name: str):
    if not price:
        print(f'  ❌ 無法取得股價資料（可能非交易日或代號有誤）')
        return
    change = price.get('change', 0)
    arrow = '▲' if change > 0 else ('▼' if change < 0 else '─')
    color_sign = '+' if change >= 0 else ''
    print(f"  收盤價：{price.get('close', 'N/A'):.2f}  {arrow} {color_sign}{change:.2f}")
    print(f"  開/高/低：{price.get('open', 'N/A'):.2f} / "
          f"{price.get('high', 'N/A'):.2f} / {price.get('low', 'N/A'):.2f}")
    vol = price.get('volume', 0)
    print(f"  成交量：{vol:,.0f} 股（{vol/1000:.0f} 張）" if vol else "  成交量：N/A")
    print(f"  資料來源：{price.get('source', 'N/A')}｜日期：{price.get('date', 'N/A')}")


def print_institutional_block(inst: dict):
    if 'error' in inst:
        print(f"  ❌ {inst['error']}")
        return
    f = inst['foreign']
    t = inst['trust']
    d = inst['dealer']
    total = inst['total']
    date = inst.get('latest_date', '')

    print(f"  分析期間：近 {inst['days_analyzed']} 個交易日（至 {date}）")
    print()
    print(f"  {'法人':<6} {'最新淨買賣':>10} {'方向':>4} {'連續':>4} {'累計':>10}")
    print(f"  {'-'*42}")
    for label, data in [('外資', f), ('投信', t), ('自營', d), ('合計', total)]:
        net = data.get('latest_net', 0)
        cum = data.get('cumsum', 0)
        cons = data.get('consecutive', 0)
        direc = data.get('direction', '')
        net_str = f"{net:+,}"
        cum_str = f"{cum:+,}"
        dir_icon = '📈' if direc == '買超' else '📉'
        print(f"  {label:<6} {net_str:>10} {dir_icon}{direc:>3} {cons:>3}天 {cum_str:>10}")

    if inst.get('signals'):
        print()
        for s in inst['signals']:
            print(f"  {s}")


def print_margin_block(margin: dict):
    if 'error' in margin:
        print(f"  ❌ {margin['error']}")
        return
    m = margin['margin']
    s = margin['short']
    date = margin.get('latest_date', '')

    print(f"  資料日期：{date}（近 {margin['days_analyzed']} 個交易日）")
    print()
    print(f"  融資餘額：{m['balance']:,} 張"
          f"  日變化：{m['change']:+,}（{m['change_pct']:+.1f}%）")
    print(f"  融資 5 日趨勢：{m['trend_5d']:+,} 張 [{m['trend_5d_label']}]")
    usage = margin.get('margin_usage_pct', 'N/A')
    usage_str = f"{usage:.1f}%" if isinstance(usage, (int, float)) else usage
    print(f"  融資使用率：{usage_str}")
    print()
    print(f"  融券餘額：{s['balance']:,} 張  券資比：{s['ratio_pct']:.1f}%")

    if margin.get('signals'):
        print()
        for s in margin['signals']:
            print(f"  {s}")


def print_valuation_block(val: dict):
    status = val.get('status')
    if status:
        print(f"  {status}")
        for note in val.get('notes', []):
            print(f"    → {note}")
        return

    val_type = val.get('valuation_type', '生技股')

    if '生技' in str(val_type) or 'pipeline' in str(val).lower():
        products = val.get('pipeline_products', [])
        if products:
            print(f"  {'產品':<12} {'階段':<8} {'成功率':>6} {'rNPV(USD億)':>12} {'rNPV(TWD百萬)':>14}")
            print(f"  {'-'*56}")
            for p in products:
                print(f"  {p['name']:<12} {p['phase']:<8} "
                      f"{p['prob_success']*100:>5.0f}% "
                      f"{p['rnpv_bn']:>12.4f} "
                      f"{p['rnpv_twd_mn']:>14,.0f}")
            print(f"  {'-'*56}")
            total_usd = val.get('total_pipeline_rnpv_usd_bn', 0)
            total_twd = val.get('total_pipeline_twd_mn', 0)
            print(f"  {'Pipeline 合計':<20} {total_usd:>12.4f} {total_twd:>14,.0f}")

        cash = val.get('cash_twd_mn')
        if cash:
            print(f"\n  現金：{cash:,.0f} 百萬台幣")
        total = val.get('total_value_twd_mn', 0)
        if total:
            print(f"  估算總價值（rNPV + 現金）：{total:,.0f} 百萬台幣")

        nav = val.get('nav_per_share_twd')
        price = val.get('current_price')
        prem = val.get('premium_vs_nav_pct')
        if nav:
            print(f"\n  每股 NAV 估算：{nav:.2f} 元")
        if price and nav:
            print(f"  當前股價：{price:.2f} 元  vs NAV 溢/折價：{prem:+.1f}%")

        runway = val.get('cash_runway_months')
        if runway:
            icon = '🔴' if runway < 12 else ('⚠️' if runway < 18 else '✅')
            print(f"\n  {icon} 現金跑道：{runway:.1f} 個月")

        if val.get('runway_alert'):
            print(f"  {val['runway_alert']}")

        print(f"\n  📌 {val.get('valuation_note', '')}")

    else:
        # 一般股票
        metrics = val.get('metrics', {})
        print(f"  估值類型：{val.get('valuation_type', '')}")
        print(f"  市值：{val.get('market_cap_mn', 0):,.0f} 百萬台幣\n")
        for k, v in metrics.items():
            if v is not None:
                print(f"  {k:<20} {v}")
        fair = val.get('fair_value_range_twd', {})
        if any(fair.values()):
            lo = fair.get('低估區', 'N/A')
            hi = fair.get('合理上限', 'N/A')
            print(f"\n  合理股價區間（P/E 法）：{lo:.1f} ~ {hi:.1f} 元")
        ref = val.get('sector_pe_reference', '')
        if ref:
            print(f"  {ref}")
        for sig in val.get('signals', []):
            print(f"  {sig}")


def print_full_report(stock_reports: list[dict]):
    """輸出所有股票的完整報告"""
    print_header('台灣生技股分析報告')

    for rpt in stock_reports:
        code = rpt['code']
        name = rpt['name']
        print(f'\n{"━"*70}')
        print(f'  ▶ {name}（{code}）')
        print(f'{"━"*70}')

        # 股價
        print(f'\n  【股價行情】')
        print_price_block(rpt.get('price'), name)

        # 三大法人
        print(f'\n  【三大法人籌碼】')
        print_institutional_block(rpt.get('chip', {}).get('institutional', {}))

        # 融資融券
        print(f'\n  【融資融券籌碼】')
        print_margin_block(rpt.get('chip', {}).get('margin', {}))

        # 估值
        print(f'\n  【估值分析】')
        if rpt.get('valuation'):
            print_valuation_block(rpt['valuation'])

        # 彙整警示
        all_alerts = rpt.get('all_alerts', [])
        if all_alerts:
            print(f'\n  【⚡ 示警彙整】')
            from alerts import format_alert_summary
            print(format_alert_summary(all_alerts))

    print(f'\n{DIVIDER}')
    print('  ⚠️  本報告僅供參考，所有分析均基於公開資訊，不構成投資建議。')
    print('  ⚠️  生技股風險極高，任何決策請自行判斷並承擔風險。')
    print(DIVIDER)
