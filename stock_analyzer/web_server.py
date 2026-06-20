"""
生技股分析網頁伺服器 - 行動裝置友善儀表板
使用方式：
  pip install fastapi uvicorn
  python web_server.py          # 電腦本機 http://localhost:8000
  python web_server.py --mobile # 手機可連（同一 WiFi）http://電腦IP:8000
  python web_server.py --port 8080  # 指定埠號
"""

import sys
import os
import time
import argparse
from datetime import datetime
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print('⚠️  缺少套件，請先執行：')
    print('    pip install fastapi uvicorn')
    sys.exit(1)

from config import STOCKS, PIPELINE
from catalyst import get_upcoming_catalysts, MAJOR_CONFERENCES_2026
from valuation import calc_biotech_valuation, calc_product_npv

app = FastAPI(title='台灣生技股儀表板')

# ── 簡易快取（30分鐘 TTL）──────────────────────────────────────
_cache: dict[str, tuple] = {}
CACHE_TTL = 1800  # 秒


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (data, time.time())


def _market_label(m: str) -> str:
    return {'twse': '上市', 'otc': '上櫃', 'innovation': '創新板',
            'emerging': '興櫃'}.get(m, m)


# ── API 端點 ────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_HTML)


@app.get('/api/stocks')
async def api_stocks():
    return [
        {
            'code': code,
            'name': info['name'],
            'market': info['market'],
            'type': info['type'],
            'market_label': _market_label(info['market']),
            'products_count': len(PIPELINE.get(code, {}).get('products', [])),
        }
        for code, info in STOCKS.items()
    ]


@app.get('/api/catalyst')
async def api_catalyst():
    cached = _cache_get('catalyst')
    if cached:
        return cached

    all_events = []
    for code, info in STOCKS.items():
        for ev in get_upcoming_catalysts(code, days_ahead=730):
            all_events.append({
                'code': code,
                'name': info['name'],
                'date': ev.get('date', ''),
                'description': ev.get('description', ''),
                'event_type': ev.get('event_type', ''),
                'product': ev.get('product', ''),
                'impact': ev.get('impact', 'medium'),
                'direction': ev.get('direction', 'binary'),
                'notes': ev.get('notes', ''),
                'days_left': ev.get('days_left'),
            })

    conferences = [
        {'name': c['name'], 'full': c['full'],
         'period': c['period'], 'focus': c['focus']}
        for c in MAJOR_CONFERENCES_2026
    ]

    result = {
        'events': all_events,
        'conferences': conferences,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    _cache_set('catalyst', result)
    return result


@app.get('/api/stock/{code}')
async def api_stock(code: str):
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')

    cached = _cache_get(f'stock_{code}')
    if cached:
        return cached

    name = STOCKS[code]['name']
    stock_type = STOCKS[code]['type']

    try:
        from fetcher import get_price, get_price_history
        from chip import full_chip_report
        from alerts import check_price_alerts, check_chip_alerts, check_valuation_alerts

        price = get_price(code)
        price_hist = get_price_history(code, 20)
        chip = full_chip_report(code, name)

        val = None
        val_alerts = []
        if stock_type == 'biotech':
            share_price = price.get('close', 0) if price else 0
            val = calc_biotech_valuation(code, name, share_price=share_price)
            val_alerts = check_valuation_alerts(code, name, val)

        all_alerts = (check_price_alerts(code, name, price_hist)
                      + check_chip_alerts(chip)
                      + val_alerts)

        result = {
            'code': code, 'name': name, 'type': stock_type,
            'price': price, 'chip': chip,
            'valuation': val, 'alerts': all_alerts,
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        _cache_set(f'stock_{code}', result)
        return result

    except Exception as e:
        return JSONResponse(status_code=500, content={
            'error': str(e), 'code': code, 'name': name,
            'hint': '確認電腦有連上台灣網路，且今天是交易日（週一~週五）',
        })


@app.get('/api/pipeline/{code}')
async def api_pipeline(code: str):
    if code not in STOCKS:
        raise HTTPException(404, f'股票代號 {code} 不在監控清單')
    prods = PIPELINE.get(code, {}).get('products', [])
    return {
        'code': code,
        'name': STOCKS[code]['name'],
        'type': STOCKS[code]['type'],
        'products': [calc_product_npv(p) for p in prods],
    }


# ── 網頁 HTML（行動裝置友善）──────────────────────────────────

_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>台灣生技股儀表板</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"微軟正黑體","Noto Sans TC",sans-serif;
     background:#f0f4f8;color:#222;font-size:15px;line-height:1.5;}
.hdr{background:linear-gradient(135deg,#1a237e,#3949ab);color:#fff;
     padding:14px 16px;text-align:center;}
.hdr h1{font-size:17px;font-weight:700;}
.hdr p{font-size:11px;opacity:.75;margin-top:3px;}
.sgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;
        padding:10px;background:#e8edf5;}
@media(min-width:600px){.sgrid{grid-template-columns:repeat(4,1fr);}}
.scard{background:#fff;border-radius:10px;padding:12px;
       box-shadow:0 1px 4px rgba(0,0,0,.1);cursor:pointer;
       border:2px solid transparent;transition:border-color .15s;user-select:none;}
.scard.sel{border-color:#1a237e;}
.scode{font-size:19px;font-weight:700;color:#1a237e;}
.sname{font-size:13px;color:#555;}
.badge{display:inline-block;padding:1px 7px;border-radius:12px;
       font-size:10px;font-weight:600;margin-top:3px;}
.bb{background:#e8f5e9;color:#2e7d32;}
.bg{background:#e3f2fd;color:#1565c0;}
.mlbl{font-size:10px;color:#999;margin-top:2px;}
.tabs{display:flex;background:#fff;border-bottom:2px solid #e0e0e0;
      overflow-x:auto;-webkit-overflow-scrolling:touch;}
.tab{padding:11px 14px;cursor:pointer;white-space:nowrap;color:#777;
     border-bottom:3px solid transparent;font-size:13px;}
.tab.on{color:#1a237e;border-bottom-color:#1a237e;font-weight:600;}
.wrap{padding:10px;max-width:900px;margin:0 auto;}
.card{background:#fff;border-radius:10px;padding:14px;margin-bottom:10px;
      box-shadow:0 1px 5px rgba(0,0,0,.08);}
.ct{font-size:15px;font-weight:700;color:#1a237e;margin-bottom:10px;}
.loading{text-align:center;padding:40px;color:#aaa;}
.sp{width:36px;height:36px;border:4px solid #ddd;border-top-color:#1a237e;
    border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 10px;}
@keyframes spin{to{transform:rotate(360deg);}}
.ad{background:#ffebee;border-left:4px solid #e53935;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.aw{background:#fff8e1;border-left:4px solid #fb8c00;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.ap{background:#e8f5e9;border-left:4px solid #43a047;padding:9px 11px;
    border-radius:4px;margin-bottom:7px;}
.alb{font-size:11px;color:#888;margin-bottom:2px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{background:#f5f5f5;padding:7px 6px;text-align:left;font-size:11px;color:#666;white-space:nowrap;}
td{padding:7px 6px;border-bottom:1px solid #f0f0f0;vertical-align:middle;}
.ci{background:#f8f4ff;border-left:4px solid #7c4dff;padding:11px 12px;
    border-radius:6px;margin-bottom:8px;}
.cm{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}
.ck{font-weight:700;font-size:13px;}
.ch{color:#d50000;font-size:12px;font-weight:600;}
.cn{color:#7c4dff;font-size:12px;}
.ce{font-size:14px;}
.cno{font-size:11px;color:#888;margin-top:4px;}
.pf{display:flex;align-items:center;flex-wrap:wrap;gap:2px;margin:6px 0;}
.ph{font-size:10px;padding:2px 6px;border-radius:8px;white-space:nowrap;}
.phd{background:#e8f5e9;color:#43a047;}
.phc{background:#1a237e;color:#fff;font-weight:700;}
.phf{background:#f0f0f0;color:#bbb;}
.pha{color:#ccc;font-size:10px;}
.npvt{font-weight:700;background:#f9f9f9;}
.pb{font-size:32px;font-weight:700;}
.up{color:#e53935;}.dn{color:#43a047;}.fl{color:#757575;}
.edu{background:#e3f2fd;border-radius:7px;padding:9px 11px;
     font-size:12px;color:#1565c0;margin-bottom:10px;}
.edu b{color:#0d47a1;}
.sg{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;}
.sc{background:#fafafa;border-radius:6px;padding:8px 10px;}
.sc .lb{font-size:11px;color:#888;}.sc .vl{font-size:15px;font-weight:700;}
.cof{display:flex;justify-content:space-between;align-items:center;
     padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px;}
.cnm{font-weight:600;}.cdt{font-size:11px;color:#888;}
.empty{text-align:center;padding:40px;color:#bbb;font-size:14px;}
</style>
</head>
<body>
<div class="hdr">
  <h1>🔬 台灣生技股儀表板</h1>
  <p>漢康-KY(7827)&nbsp;·&nbsp;康霈(6919)&nbsp;·&nbsp;泰合(6467)&nbsp;·&nbsp;竟天(6917)</p>
</div>
<div id="sg" class="sgrid"></div>
<div class="tabs" id="tb">
  <div class="tab on"  data-t="cat"  onclick="sw(this)">📅 催化劑</div>
  <div class="tab"     data-t="chip" onclick="sw(this)">📊 籌碼</div>
  <div class="tab"     data-t="val"  onclick="sw(this)">💰 估值</div>
  <div class="tab"     data-t="ale"  onclick="sw(this)">⚡ 示警</div>
  <div class="tab"     data-t="pip"  onclick="sw(this)">🧬 管線</div>
</div>
<div class="wrap" id="mc">
  <div class="loading"><div class="sp"></div><p>載入中...</p></div>
</div>
<script>
var stocks=[],sel=null,tab="cat",cache={};
async function init(){
  try{
    stocks=await jget("/api/stocks");
    rg();rt();
  }catch(e){
    mc("\\u767c\\u751f\\u932f\\u8aa4\\uff1a"+e.message);
  }
}
function $(i){return document.getElementById(i);}
function mc(h){$("mc").innerHTML=h;}
function rg(){
  $("sg").innerHTML=stocks.map(function(s){
    return '<div class="scard'+(sel===s.code?" sel":"")
      +'" onclick="ss(\''+s.code+'\')">'
      +'<div class="scode">'+s.code+'</div>'
      +'<div class="sname">'+s.name+'</div>'
      +'<div><span class="badge '+(s.type==="biotech"?"bb":"bg")+'">'
      +(s.type==="biotech"?"🔬生技":"📈一般")+'</span></div>'
      +'<div class="mlbl">'+s.market_label+"&nbsp;·&nbsp;"+s.products_count+"項產品</div>"
      +"</div>";
  }).join("");
}
function ss(c){sel=(sel===c)?null:c;rg();rt();}
function sw(el){
  tab=el.getAttribute("data-t");
  document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("on");});
  el.classList.add("on");rt();
}
function rt(){
  ({cat:tCat,chip:tChip,val:tVal,ale:tAle,pip:tPip})[tab]();
}

/* ── 催化劑 ── */
async function tCat(){
  mc(ld("催化劑日曆"));
  try{
    var d=await jcached("/api/catalyst");
    var evs=d.events||[];
    if(sel)evs=evs.filter(function(e){return e.code===sel;});
    evs.sort(function(a,b){return(a.days_left===null?9999:a.days_left)-(b.days_left===null?9999:b.days_left);});
    var h=edu("催化劑是可能讓股價大漲或大跌的關鍵事件，例如：<b>臨床數據公布、FDA審查結果、授權合作宣布</b>。"
      +"<br>🔴高影響事件成功=可能漲30~100%，失敗=可能跌30~60%，要特別留意。");
    if(!evs.length){h+='<div class="empty">📭 無催化劑事件</div>';}
    else{
      h+=evs.map(function(e){
        var dc=e.direction==="positive"?"color:#2e7d32":e.direction==="negative"?"color:#c62828":"color:#e65100";
        var di=e.direction==="positive"?"📈":e.direction==="negative"?"📉":"⚡";
        var ii=e.impact==="high"?'<span style="color:#e53935">🔴高影響</span>'
                :e.impact==="medium"?'<span style="color:#fb8c00">🟡中影響</span>'
                :'<span style="color:#43a047">🟢低影響</span>';
        return '<div class="ci">'
          +'<div class="cm"><span class="ck">'+e.name+"("+e.code+")</span>"
          +'<span>'+dl(e.days_left,e.date)+"</span></div>"
          +'<div class="ce"><span style="'+dc+'">'+di+"</span> "+e.description+"</div>"
          +'<div style="font-size:11px;margin-top:3px;">'+ii+" · "+e.product+"</div>"
          +(e.notes?'<div class="cno">💬 '+e.notes+"</div>":"")
          +"</div>";
      }).join("");
    }
    h+='<div class="card"><div class="ct">🏥 重要國際醫學年會（2026）</div>'
      +edu("生技公司常在這些年會發表臨床數據。<b>公布前一週往往提前炒作，公布當天大幅波動</b>，小心追高。")
      +(d.conferences||[]).map(function(c){
          return '<div class="cof"><div><div class="cnm">'+c.name+" "+c.full+"</div>"
            +'<div style="font-size:11px;color:#7c4dff">焦點：'+c.focus+"</div></div>"
            +'<div class="cdt">'+c.period+"</div></div>";
        }).join("")+"</div>";
    mc(h);
  }catch(e){mc(err(e.message));}
}

/* ── 籌碼 ── */
async function tChip(){
  if(!sel){mc(nos());return;}
  mc(ld("籌碼資料（首次約10~30秒）"));
  try{
    var d=await jcached("/api/stock/"+sel);
    if(d.error){mc(nerr(d.error,d.hint));return;}
    var chip=d.chip||{},inst=chip.institutional||{},marg=chip.margin||{};
    var h=edu("<b>三大法人</b>是市場主力：外資（外國大機構）、投信（台灣基金）、自營商（券商自己錢）。"
      +"<br>他們連續買進=強力看多；突然大量賣出=要警戒。"
      +"<br><b>融資</b>=借錢買股（槓桿），融資增+股價跌=最危險組合。<b>融券</b>=借股放空。");
    if(!inst.error){
      h+='<div class="card"><div class="ct">🏦 三大法人 <span style="font-size:12px;font-weight:400;color:#888">近'+(inst.days_analyzed||"?")+"個交易日</span></div>"
        +"<table><tr><th>法人</th><th>今日淨買賣(張)</th><th>方向</th><th>連續</th><th>累計(張)</th></tr>"
        +["foreign","trust","dealer","total"].map(function(k){
          var lb={foreign:"外資",trust:"投信",dealer:"自營",total:"合計"}[k];
          var di=inst[k]||{},net=di.latest_net||0,cum=di.cumsum||0;
          return'<tr'+(k==="total"?' style="font-weight:700;background:#fafafa"':"")+">"
            +"<td>"+lb+"</td>"
            +'<td class="'+(net>0?"up":net<0?"dn":"fl")+'">'+fs(net)+"</td>"
            +"<td>"+(di.direction==="買超"?"📈 買":"📉 賣")+"</td>"
            +"<td>"+(di.consecutive||0)+"天</td>"
            +'<td class="'+(cum>0?"up":cum<0?"dn":"")+'">'+fs(cum)+"</td>"
            +"</tr>";
        }).join("")+"</table>"
        +(inst.signals||[]).map(function(s){return'<div style="margin-top:6px;font-size:13px">'+s+"</div>";}).join("")
        +edu("📖 <b>外資+投信同向買超3天以上</b>→強看多信號。外資是最大主力，動向最重要。")
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 三大法人資料無法取得（非交易日或網路問題）</p></div>';
    }
    if(!marg.error){
      var m=marg.margin||{},sh=marg.short||{};
      h+='<div class="card"><div class="ct">💳 融資融券 <span style="font-size:12px;font-weight:400;color:#888">'+(marg.latest_date||"")+"</span></div>"
        +"<table><tr><th>項目</th><th>數值</th><th>說明</th></tr>"
        +"<tr><td>融資餘額</td><td>"+fn(m.balance)+" 張</td><td>借錢買股的人持有量</td></tr>"
        +'<tr><td>今日增減</td><td class="'+(m.change>0?"up":m.change<0?"dn":"")+'">'+fs(m.change)+" 張</td><td>正數=槓桿增加</td></tr>"
        +"<tr><td>5日趨勢</td><td>"+fs(m.trend_5d)+" 張</td><td>"+(m.trend_5d_label||"")+"</td></tr>"
        +"<tr><td>融資使用率</td><td>"+fp(marg.margin_usage_pct)+"</td><td>使用率越高越危險</td></tr>"
        +"<tr><td>融券餘額</td><td>"+fn(sh.balance)+" 張</td><td>放空者持有量</td></tr>"
        +"<tr><td>券資比</td><td>"+((sh.ratio_pct||0).toFixed(1))+"%</td><td>&lt;15%正常，&gt;25%空頭強勢</td></tr>"
        +"</table>"
        +(marg.signals||[]).map(function(s){return'<div style="margin-top:6px;font-size:13px">'+s+"</div>";}).join("")
        +edu("📖 <b>最危險組合</b>：融資增加＋股價下跌。代表散戶用借來的錢攤平，可能引發斷頭連鎖賣壓。")
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 融資融券資料無法取得</p></div>';
    }
    mc(h);
  }catch(e){mc(err(e.message));}
}

/* ── 估值 ── */
async function tVal(){
  if(!sel){mc(nos());return;}
  mc(ld("估值計算"));
  try{
    var d=await jcached("/api/stock/"+sel);
    if(d.error){mc(nerr(d.error,d.hint));return;}
    var val=d.valuation,price=d.price;
    var h=edu("<b>生技股為何不用本益比(P/E)？</b>"
      +"<br>本益比=股價÷每股獲利。但生技股<b>還沒賺錢</b>，所以P/E無法計算。"
      +"<br>改用 <b>rNPV法</b>=未來可能賺多少×成功機率×時間折現，是業界標準估值法。"
      +"<br>⚠️ 市場情緒往往遠高於rNPV（炒夢），也可能遠低於（恐慌拋售），請謹慎判斷。");
    if(price){
      var chg=price.change||0,cls=chg>0?"up":chg<0?"dn":"fl";
      h+='<div class="card"><div class="ct">📈 最新股價</div>'
        +'<div class="pb '+cls+'">'+(price.close||"N/A")+'</div>'
        +'<div style="margin-top:4px;font-size:14px" class="'+cls+'">'
        +(chg>0?"▲ +":chg<0?"▼ ":"─ ")+Math.abs(chg).toFixed(2)+" 元</div>"
        +'<div class="sg">'
        +sc("開盤",price.open)+sc("最高",price.high)
        +sc("最低",price.low)+sc("成交量",fn(Math.round((price.volume||0)/1000))+"張")
        +"</div>"
        +'<div style="font-size:11px;color:#888;margin-top:6px">資料日期：'+(price.date||"")+" · 來源："+(price.source||"")+"</div>"
        +"</div>";
    }else{
      h+='<div class="card"><p style="color:#999">⚠️ 股價資料無法取得（非交易日或網路問題）</p></div>';
    }
    if(val&&!val.status){
      var prods=val.pipeline_products||[];
      h+='<div class="card"><div class="ct">💊 Pipeline rNPV 估值</div>'
        +"<table><tr><th>產品</th><th>階段</th><th>成功率</th><th>rNPV(億台幣)</th></tr>"
        +prods.map(function(p){
          return"<tr><td style='font-size:12px'>"+p.name+"</td>"
            +"<td>"+pb(p.phase)+"</td>"
            +"<td>"+(p.prob_success*100).toFixed(0)+"%</td>"
            +"<td style='font-weight:600'>"+(p.rnpv_twd_mn/100).toFixed(1)+"</td></tr>";
        }).join("")
        +'<tr class="npvt"><td colspan="3">Pipeline 合計</td>'
        +"<td>"+((val.total_pipeline_twd_mn||0)/100).toFixed(1)+" 億台幣</td></tr>"
        +"</table>"
        +(val.valuation_note?'<div class="edu" style="margin-top:8px">📌 '+val.valuation_note+"</div>":"")
        +"</div>";
      if(val.cash_runway_months){
        var rw=val.cash_runway_months,ri=rw<12?"🔴":rw<18?"⚠️":"✅";
        h+='<div class="card">'+ri+" <b>現金跑道："+rw.toFixed(1)+" 個月</b>"
          +'<div style="font-size:12px;color:#888;margin-top:4px">現金不夠就要再募資（稀釋股本），跑道越短風險越高。</div>'
          +"</div>";
      }else{
        h+='<div class="card" style="font-size:13px;color:#888">ℹ️ 現金跑道資料需手動更新財報（'
          +"config.py 填入 cash_twd_mn 和 burn_rate_twd_mn）。"
          +"<br>提醒：生技股現金跑道非常重要，建議每季查閱財報！</div>";
      }
    }else if(val&&val.status){
      h+='<div class="card"><p>⚠️ '+val.status+"</p></div>";
    }
    mc(h);
  }catch(e){mc(err(e.message));}
}

/* ── 示警 ── */
async function tAle(){
  mc(ld("示警掃描"));
  var codes=sel?[sel]:stocks.map(function(s){return s.code;});
  var all=[];
  for(var i=0;i<codes.length;i++){
    try{
      var d=await jcached("/api/stock/"+codes[i]);
      if(d.alerts)(d.alerts).forEach(function(a){all.push(Object.assign({},a,{code:codes[i],sn:d.name}));});
    }catch(e){}
  }
  var h=edu("<b>示警等級：</b>"
    +"<br>🔴 危險 = 需立即關注（融資斷頭風險、現金快耗盡等）"
    +"<br>⚠️ 注意 = 持續觀察，未來可能惡化"
    +"<br>✅ 正面 = 有利訊號（不保證上漲，仍需綜合判斷）");
  if(!all.length){
    h+='<div class="empty">✅ 目前無示警<br><span style="font-size:12px">（或資料無法取得，確認已連上台灣網路且是交易日）</span></div>';
  }else{
    var o={"🔴":0,"⚠️":1,"✅":2};
    all.sort(function(a,b){return(o[a.level]||9)-(o[b.level]||9);});
    h+=all.map(function(a){
      var c=a.level==="🔴"?"ad":a.level==="⚠️"?"aw":"ap";
      return'<div class="'+c+'"><div class="alb">'+a.sn+"("+a.code+")</div>"
        +a.level+" "+a.msg+"</div>";
    }).join("");
  }
  mc(h);
}

/* ── 研發管線 ── */
async function tPip(){
  mc(ld("研發管線"));
  var codes=sel?[sel]:stocks.map(function(s){return s.code;});
  var h=edu("<b>藥物研發各階段成功率（業界統計）：</b>"
    +"<br>Phase1(安全性)→52% | Phase2(初步療效)→28% | Phase3(大規模)→57% | NDA審查→85%"
    +"<br>累計從Phase1到上市的整體成功率約 <b>8~12%</b>（非常低）。"
    +"<br>📊 Phase3成功→股價通常翻倍；Phase3失敗→通常腰斬。");
  for(var i=0;i<codes.length;i++){
    try{
      var d=await jcached("/api/pipeline/"+codes[i]);
      h+='<div class="card"><div class="ct">🧬 '+d.name+"("+d.code+")</div>"
        +(d.products||[]).map(function(p){
          return'<div style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #f0f0f0">'
            +'<div style="font-weight:600;margin-bottom:2px">'+p.name+"</div>"
            +'<div style="font-size:12px;color:#666;margin-bottom:6px">'+p.indication+"｜"+p.territory+"</div>"
            +pf(p.phase)
            +'<div class="sg" style="margin-top:8px">'
            +sc("成功率",(p.prob_success*100).toFixed(0)+"%")
            +sc("距上市","約"+p.years_to_mkt+"年")
            +sc("峰值銷售","USD "+p.peak_sales_bn+"B")
            +sc("rNPV",(p.rnpv_twd_mn/100).toFixed(1)+"億台幣")
            +"</div></div>";
        }).join("")
        +(d.products.length===0?'<p style="color:#bbb;font-size:13px">尚無產品資料</p>':"")
        +"</div>";
    }catch(e){}
  }
  mc(h);
}

/* ── Helper ── */
function ld(w){return'<div class="loading"><div class="sp"></div><p>載入'+w+'...</p></div>';}
function nos(){return'<div class="empty">👆 請先點選上方股票<br><span style="font-size:12px;color:#bbb">再點一次可取消篩選，顯示全部</span></div>';}
function err(m){return'<div class="card"><p style="color:red">⚠️ 發生錯誤：'+m+"</p></div>";}
function nerr(m,h){return'<div class="card"><p style="color:#e53935">⚠️ '+m+"</p>"+(h?'<p style="margin-top:8px;font-size:13px;color:#888">💡 '+h+"</p>":"")+"</div>";}
function edu(t){return'<div class="edu">💡 '+t+"</div>";}
function sc(l,v){return'<div class="sc"><div class="lb">'+l+'</div><div class="vl">'+(v===null||v===undefined?"N/A":v)+"</div></div>";}
function fn(n){if(n===null||n===undefined)return"N/A";return Number(n).toLocaleString();}
function fs(n){if(n===null||n===undefined)return"N/A";return(n>=0?"+":"")+fn(n);}
function fp(n){if(n===null||n===undefined||n==="N/A")return"N/A";return parseFloat(n).toFixed(1)+"%";}
function dl(days,ds){
  if(days===null||days===undefined)return'<span class="cn">📅 '+ds+"</span>";
  if(days<0)return'<span class="cn">'+Math.abs(days)+"天前</span>";
  if(days===0)return'<span class="ch">【今日！】</span>';
  if(days<=7)return'<span class="ch">⚡ '+days+"天後</span>";
  if(days<=30)return'<span style="color:#e65100;font-size:12px">'+days+"天後</span>";
  return'<span class="cn">'+Math.ceil(days/30)+"個月後</span>";
}
function pb(ph){
  var c={"Pre-IND":"#90a4ae","Phase1":"#64b5f6","Phase2":"#4fc3f7",
          "Phase3":"#4db6ac","NDA/BLA":"#ff8a65","Approved":"#81c784"}[ph]||"#90a4ae";
  return'<span style="background:'+c+'22;color:'+c+';padding:2px 7px;border-radius:8px;font-size:11px;font-weight:600">'+ph+"</span>";
}
function pf(cur){
  var phs=["Pre-IND","Phase1","Phase2","Phase3","NDA/BLA","Approved"];
  var idx=phs.indexOf(cur);
  return'<div class="pf">'+phs.map(function(p,i){
    var c=i<idx?"phd":i===idx?"phc":"phf";
    return'<span class="ph '+c+'">'+p+"</span>"+(i<phs.length-1?'<span class="pha">›</span>':"");
  }).join("")+"</div>";
}
async function jcached(url){
  if(cache[url]&&cache[url].ts&&(Date.now()-cache[url].ts<1800000))return cache[url].data;
  var data=await jget(url);cache[url]={data:data,ts:Date.now()};return data;
}
async function jget(url){
  var r=await fetch(url);if(!r.ok)throw new Error("HTTP "+r.status);return r.json();
}
init();
</script>
</body>
</html>'''


# ── 主程式 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='生技股分析網頁伺服器')
    parser.add_argument('--mobile', action='store_true',
                        help='開放區域網路（手機同一WiFi可連）')
    parser.add_argument('--port', type=int, default=8000, help='埠號（預設8000）')
    args = parser.parse_args()

    host = '0.0.0.0' if args.mobile else '127.0.0.1'

    print('=' * 56)
    print('  🔬 台灣生技股分析儀表板 已啟動')
    print()
    if args.mobile:
        print('  📱 手機可連模式（同一 WiFi）：')
        _print_ip(args.port)
    else:
        print(f'  💻 電腦瀏覽器開啟：http://localhost:{args.port}')
        print()
        print('  提示：想讓手機連線請改用：python web_server.py --mobile')
    print()
    print('  ✅ 催化劑日曆（快速）')
    print('  ✅ 三大法人籌碼 / 融資融券（需台灣IP）')
    print('  ✅ rNPV估值分析（本地計算，快速）')
    print('  ✅ 示警系統')
    print('  ✅ 研發管線總覽')
    print()
    print('  按 Ctrl+C 停止')
    print('=' * 56)

    uvicorn.run(app, host=host, port=args.port, log_level='warning')


def _print_ip(port: int) -> None:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        print(f'  手機瀏覽器開啟：http://{ip}:{port}')
        print(f'  電腦也可用：    http://localhost:{port}')
    except Exception:
        print(f'  手機瀏覽器開啟：http://電腦IP:{port}')
        print('  （先在命令提示字元輸入 ipconfig 查看電腦 IP）')
    print()


if __name__ == '__main__':
    main()
