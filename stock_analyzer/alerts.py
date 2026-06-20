"""
示警模組
整合所有警示條件並輸出優先級別的警示訊息
"""

from config import ALERT_CONFIG


def check_price_alerts(code: str, name: str, price_history: list[dict]) -> list[dict]:
    """股價技術面警示"""
    alerts = []
    if len(price_history) < 5:
        return alerts

    closes = [d['close'] for d in price_history if d.get('close')]
    volumes = [d.get('volume', 0) for d in price_history if d.get('volume')]
    if not closes:
        return alerts

    current_price = closes[-1]

    # 近期高點跌幅
    recent_high = max(closes)
    drop_pct = (recent_high - current_price) / recent_high * 100 if recent_high else 0
    if drop_pct >= ALERT_CONFIG['price_drop_from_high_pct']:
        alerts.append({
            'level': '⚠️ WARNING',
            'type': '技術面',
            'msg': f'{name}({code}) 較近期高點 {recent_high:.1f} 下跌 {drop_pct:.1f}%，當前 {current_price:.1f}',
        })

    # 20 日均線
    if len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20
        if current_price < ma20:
            gap = (ma20 - current_price) / ma20 * 100
            alerts.append({
                'level': '⚠️ WATCH',
                'type': '技術面',
                'msg': f'{name}({code}) 股價 {current_price:.1f} 跌破 20 日均線 {ma20:.1f}（差 {gap:.1f}%）',
            })

    # 成交量異常（量能爆增）
    if len(volumes) >= 20:
        avg_vol = sum(volumes[-20:]) / 20
        latest_vol = volumes[-1]
        if avg_vol > 0 and latest_vol > avg_vol * ALERT_CONFIG['volume_spike_ratio']:
            ratio = latest_vol / avg_vol
            alerts.append({
                'level': '📢 NOTE',
                'type': '技術面',
                'msg': f'{name}({code}) 成交量 {latest_vol:,.0f} 股是 20 日均量 {ratio:.1f} 倍，注意主力動向',
            })

    return alerts


def check_chip_alerts(chip_report: dict) -> list[dict]:
    """從籌碼分析結果提取警示"""
    alerts = []
    code = chip_report.get('code', '')
    name = chip_report.get('name', '')

    # 三大法人
    inst = chip_report.get('institutional', {})
    for sig in inst.get('signals', []):
        level = '🔴 DANGER' if '🔴' in sig else ('⚠️ WARNING' if '⚠️' in sig else '✅ POSITIVE')
        alerts.append({'level': level, 'type': '籌碼-法人', 'msg': f'{name}({code}) {sig}'})

    # 融資融券
    margin = chip_report.get('margin', {})
    for sig in margin.get('signals', []):
        level = '🔴 DANGER' if '🔴' in sig else ('⚠️ WARNING' if '⚠️' in sig else '✅ POSITIVE')
        alerts.append({'level': level, 'type': '籌碼-融資券', 'msg': f'{name}({code}) {sig}'})

    return alerts


def check_valuation_alerts(code: str, name: str, valuation: dict) -> list[dict]:
    """估值相關警示"""
    alerts = []

    # 生技股：現金跑道
    runway_alert = valuation.get('runway_alert')
    if runway_alert:
        alerts.append({'level': '🔴 DANGER', 'type': '財務', 'msg': runway_alert})

    # 生技股：溢價過高
    prem = valuation.get('premium_vs_nav_pct')
    if prem is not None:
        if prem > 200:
            alerts.append({
                'level': '⚠️ WARNING',
                'type': '估值',
                'msg': f'{name}({code}) 股價較 rNPV 估值溢價 {prem:.0f}%，市場期待值已很高',
            })
        elif prem < -30:
            alerts.append({
                'level': '✅ POSITIVE',
                'type': '估值',
                'msg': f'{name}({code}) 股價較 rNPV 估值折價 {abs(prem):.0f}%，可能存在安全邊際',
            })

    # 一般股票：信號
    for sig in valuation.get('signals', []):
        level = '⚠️ WARNING' if '⚠️' in sig else '✅ POSITIVE'
        alerts.append({'level': level, 'type': '估值', 'msg': sig})

    return alerts


def format_alert_summary(all_alerts: list[dict]) -> str:
    """格式化輸出所有警示"""
    if not all_alerts:
        return '  （無示警）\n'

    priority = {'🔴 DANGER': 0, '⚠️ WARNING': 1, '⚠️ WATCH': 2,
                '📢 NOTE': 3, '✅ POSITIVE': 4}
    sorted_alerts = sorted(all_alerts, key=lambda x: priority.get(x['level'], 99))

    lines = []
    for a in sorted_alerts:
        lines.append(f"  {a['level']} [{a['type']}] {a['msg']}")
    return '\n'.join(lines) + '\n'
