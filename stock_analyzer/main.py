#!/usr/bin/env python3
"""
台灣生技股分析工具 - 主程式
用法：
  python main.py                    # 執行所有股票完整報告
  python main.py --chip             # 僅籌碼分析
  python main.py --price            # 僅股價
  python main.py --alert            # 僅顯示警示
  python main.py --catalyst         # 僅顯示催化劑日曆
  python main.py --intl             # 僅顯示國際市場分析
  python main.py --stock 6467       # 單一股票
  python main.py --days 10          # 分析天數（預設 20）
"""

import argparse
import sys
import time
from config import STOCKS
from fetcher import get_price, get_price_history
from chip import full_chip_report
from valuation import calc_biotech_valuation
from alerts import check_price_alerts, check_chip_alerts, check_valuation_alerts
from report import print_full_report
from catalyst import format_catalyst_report
from intl_comps import format_intl_analysis


def run_analysis(codes: list[str], days: int = 20,
                 show_chip: bool = True,
                 show_price: bool = True,
                 show_val: bool = True,
                 alert_only: bool = False) -> list[dict]:
    results = []

    for code in codes:
        info = STOCKS.get(code, {})
        name = info.get('name', code)
        stock_type = info.get('type', 'biotech')

        print(f'\n[ {name}({code}) 資料抓取中... ]')
        report = {'code': code, 'name': name, 'all_alerts': []}

        # 股價
        if show_price or alert_only:
            print('  → 股價...')
            price = get_price(code)
            report['price'] = price
            if alert_only or show_price:
                price_hist = get_price_history(code, max(days, 20))
                price_alerts = check_price_alerts(code, name, price_hist)
                report['price_history'] = price_hist
                report['all_alerts'].extend(price_alerts)

        # 籌碼
        if show_chip or alert_only:
            print('  → 籌碼（三大法人 + 融資融券）...')
            chip = full_chip_report(code, name)
            report['chip'] = chip
            chip_alerts = check_chip_alerts(chip)
            report['all_alerts'].extend(chip_alerts)

        # 估值
        if show_val or alert_only:
            if stock_type == 'biotech':
                share_price = report.get('price', {}).get('close', 0) \
                              if report.get('price') else 0
                val = calc_biotech_valuation(code, name,
                                             share_price=share_price,
                                             shares_outstanding_mn=0)
                report['valuation'] = val
                val_alerts = check_valuation_alerts(code, name, val)
                report['all_alerts'].extend(val_alerts)

        results.append(report)
        time.sleep(1)  # 避免請求過快

    return results


def main():
    parser = argparse.ArgumentParser(description='台灣生技股分析工具')
    parser.add_argument('--stock',    type=str,  help='指定單一股票代號（e.g. 6467）')
    parser.add_argument('--days',     type=int,  default=20, help='分析天數（預設20）')
    parser.add_argument('--chip',     action='store_true', help='僅顯示籌碼分析')
    parser.add_argument('--price',    action='store_true', help='僅顯示股價')
    parser.add_argument('--alert',    action='store_true', help='僅顯示示警')
    parser.add_argument('--catalyst', action='store_true', help='僅顯示催化劑日曆')
    parser.add_argument('--intl',     action='store_true', help='僅顯示國際市場比較分析')
    parser.add_argument('--list',     action='store_true', help='列出監控中的股票')
    args = parser.parse_args()

    if args.list:
        print('\n監控股票清單：')
        for code, info in STOCKS.items():
            print(f"  {code} {info['name']} ({info['type']})")
        return

    # 催化劑日曆（快速，不需抓網路）
    if args.catalyst:
        codes = [args.stock] if args.stock else list(STOCKS.keys())
        print(format_catalyst_report(codes))
        return

    # 決定要分析哪些股票
    if args.stock:
        if args.stock not in STOCKS:
            print(f'❌ 股票代號 {args.stock} 不在監控清單中。')
            print('   監控清單：' + ', '.join(f"{c}({v['name']})" for c, v in STOCKS.items()))
            sys.exit(1)
        codes = [args.stock]
    else:
        codes = list(STOCKS.keys())

    # 決定顯示哪些模組
    show_chip  = not (args.price)
    show_price = not (args.chip)
    show_val   = not (args.chip or args.price)
    alert_only = args.alert

    if args.chip:
        show_chip, show_price, show_val = True, False, False
    elif args.price:
        show_chip, show_price, show_val = False, True, False

    results = run_analysis(
        codes, days=args.days,
        show_chip=show_chip,
        show_price=show_price,
        show_val=show_val,
        alert_only=alert_only,
    )

    # 國際市場比較（附加在完整報告後）
    if args.intl or (not any([args.chip, args.price, args.alert, args.catalyst])):
        for r in results:
            from config import PIPELINE
            prods = PIPELINE.get(r['code'], {}).get('products', [])
            print(format_intl_analysis(r['code'], r['name'], prods))

    if alert_only:
        print('\n\n【⚡ 全部示警彙整】')
        from alerts import format_alert_summary
        all_a = []
        for r in results:
            all_a.extend(r.get('all_alerts', []))
        if all_a:
            print(format_alert_summary(all_a))
        else:
            print('  今日無示警')
    else:
        print_full_report(results)


if __name__ == '__main__':
    main()
