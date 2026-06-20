"""
自動排程模組
每個交易日收盤後（14:40）自動執行分析並儲存報告
使用方式：
  python scheduler.py          # 啟動排程（背景持續執行）
  python scheduler.py --now    # 立即執行一次，不啟動排程
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# ── 確認 APScheduler 已安裝 ──────────────────────────────────
try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

from config import STOCKS
from fetcher import get_price, get_price_history
from chip import full_chip_report
from valuation import calc_biotech_valuation
from alerts import check_price_alerts, check_chip_alerts, check_valuation_alerts, format_alert_summary
from catalyst import format_catalyst_report, get_upcoming_catalysts

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, 'analyzer.log'), encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)


def run_daily_report():
    """執行每日分析並儲存結果"""
    now = datetime.now()
    log.info(f'開始執行每日分析 {now.strftime("%Y-%m-%d %H:%M")}')

    report_lines = []
    alert_lines  = []
    all_alerts   = []
    codes = list(STOCKS.keys())

    for code in codes:
        name = STOCKS[code]['name']
        log.info(f'  分析 {name}({code})...')

        price      = get_price(code)
        price_hist = get_price_history(code, 20)
        chip       = full_chip_report(code, name)
        val        = calc_biotech_valuation(
            code, name,
            share_price=price.get('close', 0) if price else 0,
        )

        p_alerts = check_price_alerts(code, name, price_hist)
        c_alerts = check_chip_alerts(chip)
        v_alerts = check_valuation_alerts(code, name, val)
        stock_alerts = p_alerts + c_alerts + v_alerts
        all_alerts.extend(stock_alerts)

        # 格式化股票區塊
        close = price.get('close', 'N/A') if price else 'N/A'
        change = price.get('change', 0) if price else 0
        arrow = '▲' if change > 0 else ('▼' if change < 0 else '─')
        vol = price.get('volume', 0) if price else 0

        inst  = chip.get('institutional', {})
        f_net = inst.get('foreign', {}).get('latest_net', 0)
        t_net = inst.get('trust',   {}).get('latest_net', 0)
        total_net = inst.get('total', {}).get('latest_net', 0)
        f_cons = inst.get('foreign', {}).get('consecutive', 0)
        f_dir  = inst.get('foreign', {}).get('direction', '')

        margin   = chip.get('margin', {})
        m_bal    = margin.get('margin', {}).get('balance', 0)
        m_chg    = margin.get('margin', {}).get('change', 0)
        s_ratio  = margin.get('short', {}).get('ratio_pct', 0)

        lines = [
            f'',
            f'━━ {name}({code}) ━━',
            f'  股價：{close}  {arrow}{change:+.2f}  量：{vol/1000:.0f}張' if isinstance(close, float) else f'  股價：N/A',
            f'  外資：{f_net:+,}張（連{f_cons}天{f_dir}）  投信：{t_net:+,}張  合計：{total_net:+,}張',
            f'  融資：{m_bal:,}張 ({m_chg:+,})  券資比：{s_ratio:.1f}%',
        ]
        if stock_alerts:
            lines.append(f'  ⚡ 示警：')
            for a in stock_alerts:
                lines.append(f'    {a["level"]} {a["msg"]}')
        report_lines.extend(lines)

    # 催化劑提醒
    cat_section = format_catalyst_report(codes)
    report_lines.append(cat_section)

    # 彙整所有示警
    if all_alerts:
        alert_lines.append('\n【今日全部示警彙整】')
        alert_lines.append(format_alert_summary(all_alerts))
    else:
        alert_lines.append('\n【今日無示警】\n')

    # 組合完整報告
    header = [
        '=' * 60,
        f'  台灣生技股每日報告  {now.strftime("%Y-%m-%d %H:%M")}',
        '=' * 60,
    ]
    footer = [
        '',
        '─' * 60,
        '  ⚠️  僅供參考，不構成投資建議',
        '─' * 60,
    ]
    full_report = '\n'.join(header + report_lines + alert_lines + footer)

    # 儲存到 logs/
    date_str = now.strftime('%Y%m%d')
    log_path = os.path.join(LOG_DIR, f'report_{date_str}.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(full_report)

    print(full_report)
    log.info(f'報告已儲存：{log_path}')
    return full_report


def _is_trading_day() -> bool:
    """簡易判斷是否為台灣交易日（週一到週五，未判斷假日）"""
    return datetime.today().weekday() < 5


def main():
    parser = argparse.ArgumentParser(description='生技股自動排程分析')
    parser.add_argument('--now', action='store_true', help='立即執行一次')
    args = parser.parse_args()

    if args.now or not HAS_SCHEDULER:
        if not HAS_SCHEDULER and not args.now:
            print('⚠️  APScheduler 未安裝，改為立即執行一次')
            print('    若要排程功能，執行：pip install apscheduler\n')
        run_daily_report()
        return

    scheduler = BlockingScheduler(timezone='Asia/Taipei')
    # 每個交易日 14:40（收盤後 10 分鐘）自動執行
    scheduler.add_job(
        func=lambda: run_daily_report() if _is_trading_day() else None,
        trigger=CronTrigger(hour=14, minute=40,
                            day_of_week='mon-fri',
                            timezone='Asia/Taipei'),
        id='daily_report',
        name='每日收盤後分析',
        misfire_grace_time=300,
    )
    # 每個交易日 09:05（開盤前）再跑一次催化劑提醒
    scheduler.add_job(
        func=lambda: print(format_catalyst_report(list(STOCKS.keys()))) if _is_trading_day() else None,
        trigger=CronTrigger(hour=9, minute=5,
                            day_of_week='mon-fri',
                            timezone='Asia/Taipei'),
        id='morning_catalyst',
        name='開盤前催化劑提醒',
        misfire_grace_time=300,
    )

    print('=' * 50)
    print('  生技股自動排程已啟動')
    print('  ✅ 每個交易日 09:05  → 催化劑提醒')
    print('  ✅ 每個交易日 14:40  → 完整分析報告')
    print('  報告儲存位置：logs/report_YYYYMMDD.txt')
    print('  按 Ctrl+C 停止排程')
    print('=' * 50)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print('\n排程已停止。')


if __name__ == '__main__':
    main()
