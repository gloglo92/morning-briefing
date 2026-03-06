"""
퀀트 모닝 브리핑 텔레그램 봇 - 디버그 버전
"""

import requests
from datetime import datetime, timedelta
import yfinance as yf
import traceback
import json

TELEGRAM_TOKEN = "8051338333:AAGzZAHrV4tGCRIO3UVRpzsdpUeHRqHESMs"
CHAT_ID = "311858790"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    return response.json()

def get_prev_business_day():
    today = datetime.today()
    target = today - timedelta(days=1)
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target.strftime("%Y%m%d"), target.strftime("%Y-%m-%d")

def get_global_data():
    tickers = {
        "나스닥": "^IXIC", "S&P500": "^GSPC", "다우존스": "^DJI",
        "VIX": "^VIX", "브렌트유": "BZ=F", "금": "GC=F",
    }
    result = {}
    for name, ticker in tickers.items():
        try:
            df = yf.Ticker(ticker).history(period="5d")
            if len(df) >= 2:
                prev_close = df['Close'].iloc[-2]
                last_close = df['Close'].iloc[-1]
                change = last_close - prev_close
                pct = (change / prev_close) * 100
                result[name] = {"price": last_close, "change": change, "pct": pct}
        except Exception:
            result[name] = None
    return result

def krx_post(body):
    url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    headers = {
        "Referer": "https://data.krx.co.kr/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    resp = requests.post(url, data=body, headers=headers, timeout=20)
    data = resp.json()
    # 디버그: 응답 구조 출력
    print(f"[KRX] bld={body.get('bld','?')} keys={list(data.keys())} rows={len(data.get('output',data.get('OutBlock_1',[])))}")
    if data.get("output"):
        print(f"  첫번째 row 키: {list(data['output'][0].keys()) if data['output'] else 'empty'}")
    return data

def parse_investor(rows):
    result = {}
    for row in rows:
        # 가능한 컬럼명 탐색
        inv = row.get("INVST_TP_NM") or row.get("invstTpNm") or row.get("TRDISTT_NM") or ""
        val_str = (row.get("NETBID_TRDVAL") or row.get("netBidTrdVal") or
                   row.get("NET_BID_TRDVAL") or row.get("SELN_TRDVAL") or "0")
        val_str = str(val_str).replace(",", "").replace(" ", "")
        try:
            val = int(float(val_str) / 1e8)
        except:
            val = 0
        print(f"  투자자: [{inv}] 값: {val_str} -> {val}억")
        if "외국인" in str(inv) and "기타" not in str(inv):
            result["외국인"] = val
        elif str(inv) in ["기관합계", "기관"]:
            result["기관"] = val
        elif str(inv) == "개인":
            result["개인"] = val
    return result if result else None

def get_krx_investor(date_str, market="STK"):
    try:
        data = krx_post({
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02303",
            "locale": "ko_KR", "mktId": market, "trdDd": date_str,
            "money": "1", "askBid": "3", "share": "1", "part": "ALL", "cssId": "part1"
        })
        rows = data.get("output") or data.get("OutBlock_1") or []
        return parse_investor(rows)
    except Exception as e:
        print(f"코스피/코스닥 오류: {e}")
        return None

def get_krx_futures(date_str):
    try:
        data = krx_post({
            "bld": "dbms/MDC/STAT/standard/MDCSTAT12401",
            "locale": "ko_KR", "trdDd": date_str,
            "prodId": "KOSPI200", "money": "1", "cssId": "part1"
        })
        rows = data.get("output") or data.get("OutBlock_1") or []
        return parse_investor(rows)
    except Exception as e:
        print(f"선물 오류: {e}")
        return None

def get_krx_program(date_str):
    try:
        data = krx_post({
            "bld": "dbms/MDC/STAT/standard/MDCSTAT02601",
            "locale": "ko_KR", "trdDd": date_str, "money": "1", "cssId": "part1"
        })
        rows = data.get("output") or data.get("OutBlock_1") or []
        result = {}
        for row in rows:
            print(f"  프로그램 row: {row}")
            tp = row.get("ARB_TP_NM") or row.get("arbTpNm") or ""
            val_str = str(row.get("NETBID_TRDVAL") or row.get("netBidTrdVal") or "0").replace(",", "")
            try:
                val = int(float(val_str) / 1e8)
            except:
                val = 0
            if tp in ["차익", "비차익", "전체"]:
                result[tp] = val
        return result if result else None
    except Exception as e:
        print(f"프로그램매매 오류: {e}")
        return None

def get_krx_data():
    date_str, date_label = get_prev_business_day()
    print(f"\n[KRX 조회 날짜: {date_str}]")
    return {
        "date": date_label,
        "kospi":   get_krx_investor(date_str, "STK"),
        "kosdaq":  get_krx_investor(date_str, "KSQ"),
        "futures": get_krx_futures(date_str),
        "program": get_krx_program(date_str),
    }

def arrow(pct):
    return "🔺" if pct > 0 else ("🔻" if pct < 0 else "➡️")

def fmt_val(val):
    if val is None: return "N/A"
    return f"{'+'if val>=0 else ''}{val:,}억"

def build_message(global_data, krx_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    L.append(f"📊 <b>퀀트 모닝 브리핑</b>")
    L.append(f"⏰ {now} 기준\n")
    L.append("━━━━━━━━━━━━━━━━━━")
    L.append("🌐 <b>글로벌 지표 (전일 미국 마감)</b>")
    L.append("━━━━━━━━━━━━━━━━━━")

    for name in ["나스닥", "S&P500", "다우존스"]:
        d = global_data.get(name)
        if d:
            L.append(f"{arrow(d['pct'])} {name}: <b>{d['price']:,.2f}</b> ({d['pct']:+.2f}%)")
        else:
            L.append(f"❓ {name}: 데이터 없음")

    L.append("")
    vix = global_data.get("VIX")
    if vix: L.append(f"{arrow(vix['pct'])} VIX 공포지수: <b>{vix['price']:.2f}</b> ({vix['pct']:+.2f}%)")
    oil = global_data.get("브렌트유")
    if oil: L.append(f"{arrow(oil['pct'])} 브렌트유: <b>${oil['price']:.2f}</b> ({oil['pct']:+.2f}%)")
    gold = global_data.get("금")
    if gold: L.append(f"{arrow(gold['pct'])} 국제 금: <b>${gold['price']:,.2f}</b> ({gold['pct']:+.2f}%)")

    L.append("")
    L.append("━━━━━━━━━━━━━━━━━━")
    L.append(f"🇰🇷 <b>한국 증시 수급 ({krx_data['date']} 마감)</b>")
    L.append("━━━━━━━━━━━━━━━━━━")

    for label, key in [("코스피 현물", "kospi"), ("코스닥 현물", "kosdaq")]:
        L.append(f"\n📌 <b>{label}</b>")
        d = krx_data.get(key)
        if d:
            L.append(f"  외국인: {fmt_val(d.get('외국인'))}")
            L.append(f"  기관:   {fmt_val(d.get('기관'))}")
            L.append(f"  개인:   {fmt_val(d.get('개인'))}")
        else:
            L.append("  데이터 없음")

    L.append(f"\n📌 <b>KOSPI200 선물</b>")
    d = krx_data.get("futures")
    if d:
        L.append(f"  외국인: {fmt_val(d.get('외국인'))}")
        L.append(f"  기관:   {fmt_val(d.get('기관'))}")
        L.append(f"  개인:   {fmt_val(d.get('개인'))}")
    else:
        L.append("  데이터 없음")

    L.append(f"\n📌 <b>코스피 프로그램 매매</b>")
    d = krx_data.get("program")
    if d:
        L.append(f"  차익거래:   {fmt_val(d.get('차익'))}")
        L.append(f"  비차익거래: {fmt_val(d.get('비차익'))}")
        L.append(f"  전체:       {fmt_val(d.get('전체'))}")
    else:
        L.append("  데이터 없음")

    L.append("\n━━━━━━━━━━━━━━━━━━")
    L.append("Good morning! 오늘도 성공적인 매매 되세요 🙏")
    return "\n".join(L)

def main():
    try:
        print("📡 글로벌 데이터 수집 중...")
        global_data = get_global_data()
        print("📡 한국 증시 수급 수집 중...")
        krx_data = get_krx_data()
        print("\n📝 메시지 생성 중...")
        message = build_message(global_data, krx_data)
        print(message)
        print("\n📨 텔레그램 발송 중...")
        result = send_telegram(message)
        print("✅ 완료!" if result.get("ok") else f"❌ 실패: {result}")
    except Exception as e:
        error_msg = f"⚠️ 오류 발생\n{traceback.format_exc()}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    main()
