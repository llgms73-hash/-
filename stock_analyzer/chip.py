"""
籌碼分析模組
- 三大法人：連續買賣超、累計張數、趨勢判斷
- 融資融券：餘額變化、券資比、危險信號
"""

from fetcher import (
    get_institutional_history, get_margin_history,
    get_price_history
)
from config import ALERT_CONFIG


def analyze_institutional(code: str, name: str, days: int = 20) -> dict:
    """三大法人籌碼分析"""
    history = get_institutional_history(code, days)
    if not history:
        return {'code': code, 'error': '無法取得三大法人資料'}

    foreign_nets = [d['foreign_net'] for d in history]
    trust_nets   = [d['trust_net']   for d in history]
    dealer_nets  = [d['dealer_net']  for d in history]
    total_nets   = [d['total_net']   for d in history]

    # 連續買超/賣超天數（從最新日往回算）
    def consecutive(nets: list[int]) -> tuple[int, str]:
        if not nets:
            return 0, 'N/A'
        last = nets[-1]
        direction = '買超' if last > 0 else '賣超'
        count = 0
        for v in reversed(nets):
            if (v > 0 and direction == '買超') or (v < 0 and direction == '賣超'):
                count += 1
            else:
                break
        return count, direction

    f_days, f_dir = consecutive(foreign_nets)
    t_days, t_dir = consecutive(trust_nets)
    d_days, d_dir = consecutive(dealer_nets)
    total_days, total_dir = consecutive(total_nets)

    # 累計買賣超
    f_cumsum   = sum(foreign_nets)
    t_cumsum   = sum(trust_nets)
    d_cumsum   = sum(dealer_nets)
    total_sum  = sum(total_nets)

    # 判斷信號
    signals = []
    threshold = ALERT_CONFIG['institutional_sell_days']
    if f_dir == '賣超' and f_days >= threshold:
        signals.append(f'⚠️ 外資連續賣超 {f_days} 天')
    if t_dir == '賣超' and t_days >= threshold:
        signals.append(f'⚠️ 投信連續賣超 {t_days} 天')
    if f_dir == '買超' and f_days >= 3:
        signals.append(f'✅ 外資連續買超 {f_days} 天')
    if t_dir == '買超' and t_days >= 3:
        signals.append(f'✅ 投信連續買超 {t_days} 天')
    if total_dir == '賣超' and total_days >= threshold:
        signals.append(f'🔴 三大法人合計連續賣超 {total_days} 天')

    return {
        'code': code,
        'name': name,
        'days_analyzed': len(history),
        'latest_date': history[-1]['date'] if history else 'N/A',
        'foreign': {
            'latest_net': foreign_nets[-1] if foreign_nets else 0,
            'consecutive': f_days,
            'direction': f_dir,
            'cumsum': f_cumsum,
        },
        'trust': {
            'latest_net': trust_nets[-1] if trust_nets else 0,
            'consecutive': t_days,
            'direction': t_dir,
            'cumsum': t_cumsum,
        },
        'dealer': {
            'latest_net': dealer_nets[-1] if dealer_nets else 0,
            'consecutive': d_days,
            'direction': d_dir,
            'cumsum': d_cumsum,
        },
        'total': {
            'latest_net': total_nets[-1] if total_nets else 0,
            'consecutive': total_days,
            'direction': total_dir,
            'cumsum': total_sum,
        },
        'signals': signals,
    }


def analyze_margin(code: str, name: str, days: int = 20) -> dict:
    """融資融券籌碼分析"""
    margin_hist = get_margin_history(code, days)
    price_hist  = get_price_history(code, days)

    if not margin_hist:
        return {'code': code, 'error': '無法取得融資融券資料'}

    margin_bals  = [d['margin_bal']  for d in margin_hist]
    short_bals   = [d['short_bal']   for d in margin_hist]
    short_ratios = [d['short_ratio'] for d in margin_hist]

    # 最新一日
    latest = margin_hist[-1]
    latest_margin = latest['margin_bal']
    latest_short  = latest['short_bal']
    latest_ratio  = latest.get('short_ratio', 0)

    # 融資增減（比前一日）
    prev_margin = margin_bals[-2] if len(margin_bals) >= 2 else latest_margin
    margin_change = latest_margin - prev_margin
    margin_change_pct = (margin_change / prev_margin * 100) if prev_margin else 0

    # 融資增 + 股價跌 → 散戶攤平追跌，危險
    danger_signal = False
    if price_hist and len(price_hist) >= 2:
        latest_price = price_hist[-1]['close']
        prev_price   = price_hist[-2]['close']
        price_dropped = latest_price < prev_price
        margin_increased = margin_change > 0
        if margin_increased and price_dropped:
            danger_signal = True

    signals = []
    if danger_signal:
        signals.append('🔴 融資增加 + 股價下跌：散戶攤平，風險升高')
    if latest_ratio > ALERT_CONFIG['short_ratio_warning']:
        signals.append(f'⚠️ 券資比 {latest_ratio:.1f}% 偏高（空方壓力大）')
    if margin_change_pct > ALERT_CONFIG['margin_increase_pct']:
        signals.append(f'⚠️ 融資單日增加 {margin_change_pct:.1f}%（散戶積極追多）')
    if latest_ratio < 3 and latest_short > 0:
        signals.append(f'✅ 券資比低 ({latest_ratio:.1f}%)，空方壓力小')

    # 融資 5 日趨勢
    if len(margin_bals) >= 5:
        trend_5d = margin_bals[-1] - margin_bals[-5]
        trend_label = '增加' if trend_5d > 0 else '減少'
    else:
        trend_5d = 0
        trend_label = 'N/A'

    return {
        'code': code,
        'name': name,
        'days_analyzed': len(margin_hist),
        'latest_date': latest.get('date', 'N/A'),
        'margin': {
            'balance': latest_margin,
            'change': margin_change,
            'change_pct': round(margin_change_pct, 2),
            'trend_5d': trend_5d,
            'trend_5d_label': trend_label,
        },
        'short': {
            'balance': latest_short,
            'ratio_pct': latest_ratio,
        },
        'margin_usage_pct': latest.get('margin_usage', 'N/A'),
        'signals': signals,
    }


def analyze_institutional_from_history(history: list, code: str, name: str) -> dict:
    """三大法人籌碼分析（使用已預先抓取的資料，不再發 HTTP 請求）"""
    if not history:
        return {'code': code, 'error': '無法取得三大法人資料'}

    foreign_nets = [d['foreign_net'] for d in history]
    trust_nets   = [d['trust_net']   for d in history]
    dealer_nets  = [d['dealer_net']  for d in history]
    total_nets   = [d['total_net']   for d in history]

    def consecutive(nets):
        if not nets:
            return 0, 'N/A'
        direction = '買超' if nets[-1] > 0 else '賣超'
        count = 0
        for v in reversed(nets):
            if (v > 0 and direction == '買超') or (v < 0 and direction == '賣超'):
                count += 1
            else:
                break
        return count, direction

    f_days, f_dir = consecutive(foreign_nets)
    t_days, t_dir = consecutive(trust_nets)
    d_days, d_dir = consecutive(dealer_nets)
    total_days, total_dir = consecutive(total_nets)

    signals = []
    threshold = ALERT_CONFIG['institutional_sell_days']
    if f_dir == '賣超' and f_days >= threshold:
        signals.append(f'⚠️ 外資連續賣超 {f_days} 天')
    if t_dir == '賣超' and t_days >= threshold:
        signals.append(f'⚠️ 投信連續賣超 {t_days} 天')
    if f_dir == '買超' and f_days >= 3:
        signals.append(f'✅ 外資連續買超 {f_days} 天')
    if t_dir == '買超' and t_days >= 3:
        signals.append(f'✅ 投信連續買超 {t_days} 天')
    if total_dir == '賣超' and total_days >= threshold:
        signals.append(f'🔴 三大法人合計連續賣超 {total_days} 天')

    return {
        'code': code, 'name': name,
        'days_analyzed': len(history),
        'latest_date': history[-1]['date'] if history else 'N/A',
        'foreign':  {'latest_net': foreign_nets[-1] if foreign_nets else 0, 'consecutive': f_days, 'direction': f_dir, 'cumsum': sum(foreign_nets)},
        'trust':    {'latest_net': trust_nets[-1]   if trust_nets   else 0, 'consecutive': t_days, 'direction': t_dir, 'cumsum': sum(trust_nets)},
        'dealer':   {'latest_net': dealer_nets[-1]  if dealer_nets  else 0, 'consecutive': d_days, 'direction': d_dir, 'cumsum': sum(dealer_nets)},
        'total':    {'latest_net': total_nets[-1]   if total_nets   else 0, 'consecutive': total_days, 'direction': total_dir, 'cumsum': sum(total_nets)},
        'signals': signals,
    }


def analyze_margin_from_history(margin_hist: list, price_hist: list, code: str, name: str) -> dict:
    """融資融券籌碼分析（使用已預先抓取的資料，不再發 HTTP 請求）"""
    if not margin_hist:
        return {'code': code, 'error': '無法取得融資融券資料'}

    margin_bals = [d['margin_bal'] for d in margin_hist]
    latest = margin_hist[-1]
    latest_margin = latest['margin_bal']
    latest_short  = latest['short_bal']
    latest_ratio  = latest.get('short_ratio', 0)

    prev_margin = margin_bals[-2] if len(margin_bals) >= 2 else latest_margin
    margin_change = latest_margin - prev_margin
    margin_change_pct = (margin_change / prev_margin * 100) if prev_margin else 0

    danger_signal = False
    if price_hist and len(price_hist) >= 2:
        if (price_hist[-1]['close'] < price_hist[-2]['close']) and margin_change > 0:
            danger_signal = True

    signals = []
    if danger_signal:
        signals.append('🔴 融資增加 + 股價下跌：散戶攤平，風險升高')
    if latest_ratio > ALERT_CONFIG['short_ratio_warning']:
        signals.append(f'⚠️ 券資比 {latest_ratio:.1f}% 偏高（空方壓力大）')
    if margin_change_pct > ALERT_CONFIG['margin_increase_pct']:
        signals.append(f'⚠️ 融資單日增加 {margin_change_pct:.1f}%（散戶積極追多）')
    if latest_ratio < 3 and latest_short > 0:
        signals.append(f'✅ 券資比低 ({latest_ratio:.1f}%)，空方壓力小')

    if len(margin_bals) >= 5:
        trend_5d = margin_bals[-1] - margin_bals[-5]
        trend_label = '增加' if trend_5d > 0 else '減少'
    else:
        trend_5d, trend_label = 0, 'N/A'

    return {
        'code': code, 'name': name,
        'days_analyzed': len(margin_hist),
        'latest_date': latest.get('date', 'N/A'),
        'margin': {'balance': latest_margin, 'change': margin_change, 'change_pct': round(margin_change_pct, 2), 'trend_5d': trend_5d, 'trend_5d_label': trend_label},
        'short':  {'balance': latest_short, 'ratio_pct': latest_ratio},
        'margin_usage_pct': latest.get('margin_usage', 'N/A'),
        'signals': signals,
    }


def full_chip_report(code: str, name: str) -> dict:
    """整合三大法人 + 融資融券完整籌碼報告"""
    inst = analyze_institutional(code, name)
    margin = analyze_margin(code, name)
    return {
        'code': code, 'name': name,
        'institutional': inst, 'margin': margin,
        'all_signals': inst.get('signals', []) + margin.get('signals', []),
    }
