"""
퀀트 모닝 브리핑 텔레그램 봇
매일 오전 7시 자동 발송
"""

import requests
from datetime import datetime, timedelta
import yfinance as yf
import traceback

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
        except Exception as e:
            print(f"{name} 오류: {e}")
            result[name] = None
    return result

def get_krx_data():
    from pykrx import stock

    date_str, date_label = get_prev_business_day()
    print(f"[KRX 조회 날짜: {date_str}]")
    result = {"date": date_label}

    # 코스피 수급
    try:
        df = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSPI")
        print(f"코스피 columns: {list(df.columns)}")
        print(f"코스피 index: {list(df.index)}")
        print(df)
        net_col = [c for c in df.columns if "순매수" in c or "net" in c.lower()]
        col = net_col[0] if net_col else df.columns[-1]
        result["kospi"] = {
            "외국인": int(df.loc["외국인합계", col] / 1e8) if "외국인합계" in df.index else
                      int(df.loc["외국인", col] / 1e8) if "외국인" in df.index else 0,
            "기관":   int(df.loc["기관합계", col] / 1e8) if "기관합계" in df.index else
                      int(df.loc["기관", col] / 1e8) if "기관" in df.index else 0,
            "개인":   int(df.loc["개인", col] / 1e8) if "개인" in df.index else 0,
        }
    except Exception as e:
        print(f"코스피 오류: {e}\n{traceback.format_exc()}")
        result["kospi"] = None

    # 코스닥 수급
    try:
        df = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSDAQ")
        net_col = [c for c in df.columns if "순매수" in c or "net" in c.lower()]
        col = net_col[0] if net_col else df.columns[-1]
        result["kosdaq"] = {
            "외국인": int(df.loc["외국인합계", col] / 1e8) if "외국인합계" in df.index else
                      int(df.loc["외국인", col] / 1e8) if "외국인" in df.index else 0,
            "기관":   int(df.loc["기관합계", col] / 1e8) if "기관합계" in df.index else
                      int(df.loc["기관", col] / 1e8) if "기관" in df.index else 0,
            "개인":   int(df.loc["개인", col] / 1e8) if "개인" in df.index else 0,
        }
    except Exception as e:
        print(f"코스닥 오류: {e}")
        result["kosdaq"] = None

    # 선물 수급
    try:
        df = stock.get_futures_trading_value_by_investor(date_str, date_str, "KOSPI200")
        print(f"선물 columns: {list(df.columns)}")
        print(f"선물 index: {list(df.index)}")
        print(df)
        net_col = [c for c in df.columns if "순매수" in c or "net" in c.lower()]
        col = net_col[0] if net_col else df.columns[-1]
        result["futures"] = {
            "외국인": int(df.loc["외국인합계", col] / 1e8) if "외국인합계" in df.index else
                      int(df.loc["외국인", col] / 1e8) if "외국인" in df.index else 0,
            "기관":   int(df.loc["기관합계", col] / 1e8) if "기관합계" in df.index else
                      int(df.loc["기관", col] / 1e8) if "기관" in df.index else 0,
            "개인":   int(df.loc["개인", col] / 1e8) if "개인" in df.index else 0,
        }
    except Exception as e:
        print(f"선물 오류: {e}")
        result["futures"] = None

    # 프로그램 매매
    try:
        df = stock.get_market_net_purchases_of_programs(date_str, date_str, "KOSPI")
        print(f"프로그램 columns: {list(df.columns)}")
        print(f"프로그램 index: {list(df.index)}")
        print(df)
        # 차익/비차익/전체 합계 행 찾기
        result["program"] = {
            "차익":   int(df["차익"].sum() / 1e8) if "차익" in df.columns else 0,
            "비차익": int(df["비차익"].sum() / 1e8) if "비차익" in df.columns else 0,
            "전체":   int(df["전체"].sum() / 1e8) if "전체" in df.columns else 0,
        }
    except Exception as e:
        print(f"프로그램매매 오류: {e}\n{traceback.format_exc()}")
        result["program"] = None

    return result

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
