# 台灣生技股分析工具

監控股票：康霈(7827)、漢康-KY(6919)、泰合(6467)、竟天(6917)

## 功能

- **股價行情**：即時收盤、開高低、成交量
- **三大法人籌碼**：外資/投信/自營商買賣超、連續天數、累計張數
- **融資融券分析**：餘額、增減幅、券資比、融資增+股價跌危險信號
- **生技估值**：Pipeline rNPV（風險調整後淨現值）+ 現金跑道
- **示警系統**：自動偵測危險信號並分級顯示
- **一般股票估值**：P/E、P/B、EV/EBITDA（未來加入一般股用）

**資料來源：台灣 TWSE / TPEx 合法開放 API（無需帳號）**

## 安裝

```bash
cd stock_analyzer
pip install -r requirements.txt
```

## 使用方式

```bash
# 完整報告（所有股票）
python main.py

# 僅籌碼分析
python main.py --chip

# 僅顯示示警
python main.py --alert

# 單一股票
python main.py --stock 6467

# 分析近 30 個交易日
python main.py --days 30

# 列出監控股票
python main.py --list
```

## 填入 Pipeline 資料（重要！）

生技估值需要手動維護 `config.py` 中的 `PIPELINE` 資料：

```python
PIPELINE = {
    '6467': {  # 泰合
        'cash_twd_mn': 500,         # 最新季報現金（百萬台幣）
        'burn_rate_twd_mn': 30,     # 每季現金消耗（百萬台幣）
        'products': [
            {
                'name': 'XX-001',
                'phase': 'Phase2',
                'indication': '適應症名稱',
                'territory': '全球',
                'market_usd_bn': 5.0,    # 目標市場規模（十億美元）
                'peak_sales_bn': 0.3,    # 估算峰值銷售額（十億美元）
                'prob_success': 0.28,    # Phase2 歷史成功率
                'royalty_rate': 0.10,    # 授權金率（自銷填 1.0）
                'years_to_mkt': 4,       # 距上市預計年數
                'discount_rate': 0.15,
            },
        ],
    },
}
```

資料來源：公司法說會簡報、重大訊息、ClinicalTrials.gov

## 示警等級

| 等級 | 意義 |
|------|------|
| 🔴 DANGER | 立即注意（現金快燒完、融資+股跌） |
| ⚠️ WARNING | 風險上升（法人連賣、券資比高） |
| ⚠️ WATCH | 技術面轉弱 |
| 📢 NOTE | 量能異常，需關注 |
| ✅ POSITIVE | 正面信號 |

## 免責聲明

本工具僅供輔助分析，不構成投資建議。生技股風險極高，所有投資決策請自行判斷。
