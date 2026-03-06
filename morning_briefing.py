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

def extract_investor(df):
    """pykrx DataFrame에서 외국인/기관/개인 순매수 추출"""
    print(f"  columns: {list(df.columns)}")
    print(f"  index: {list(df.index)}")

    # 순매수 컬럼 찾기 (버전별로 다름)
    col = None
    for candidate in ["순매수", "순매수금액", "거래대금", df.columns[-1]]:
        if candidate in df.columns:
            col = candidate
            break
    if col is None:
        col = df.columns[-1]
    print(f"  사용 컬럼: {col}")

    def get_val(keys):
        for k in keys:
            if k in df.index:
                return int(df.loc[k, col] / 1e8)
        return 0

    return {
        "외국인": get_val(["외국인합계", "외국인"]),
        "기관":   get_val(["기관합계", "기관"]),
        "개인":   get_val(["개인"]),
    }

def get_krx_data():
    from pykrx import stock

    date_str, date_label = get_prev_business_day()
    print(f"[KRX 조회 날짜: {date_str}]")
    result = {"date": date_label}

    # 코스피 수급
    try:
        df = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSPI")
        result["kospi"] = extract_investor(df)
        print(f"코스피 OK: {result['kospi']}")
    except Exception as e:
        print(f"코스피 오류: {e}\n{traceback.format_exc()}")
        result["kospi"] = None

    # 코스닥 수급
    try:
        df = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSDAQ")
        result["kosdaq"] = extract_investor(df)
        print(f"코스닥 OK: {result['kosdaq']}")
    except Exception as e:
        print(f"코스닥 오류: {e}")
        result["kosdaq"] = None

    # 선물 수급 - pykrx 1.2.x 함수명 탐색
    result["futures"] = None
    for func_name in ["get_market_trading_value_by_investor_for_futures",
                      "get_futures_ohlcv_by_date",
                      "get_index_ohlcv_by_date"]:
        if hasattr(stock, func_name):
            print(f"선물 함수 발견: {func_name}")
            break
    else:
        # 대안: ETF/지수 선물 - 투자자별 데이터를 ETF로 대체
        try:
            # KODEX 200선물인버스2X ETF(233740) 대신 선물 투자자 직접 조회
            df = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSPI")
            # 선물은 별도 API가 없으면 None 처리
            print("선물: pykrx 1.2.x에서 선물 투자자 API 미지원, 건너뜀")
        except:
            pass

    # 프로그램 매매 - pykrx 1.2.x 함수명 탐색
    result["program"] = None
    prog_funcs = [f for f in dir(stock) if "program" in f.lower() or "prog" in f.lower()]
    print(f"프로그램 관련 함수: {prog_funcs}")

    for func_name in ["get_market_program_trading_value",
                      "get_program_trading_trend",
                      "get_market_trading_value_of_program"]:
        if hasattr(stock, func_name):
            try:
                fn = getattr(stock, func_name)
                df = fn(date_str, date_str, "KOSPI")
                print(f"프로그램 {func_name} OK:")
                print(df)
                result["program"] = {
                    "차익":   int(df["차익"].iloc[-1]   / 1e8) if "차익"   in df.columns else 0,
                    "비차익": int(df["비차익"].iloc[-1] / 1e8) if "비차익" in df.columns else 0,
                    "전체":   int(df["전체"].iloc[-1]   / 1e8) if "전체"   in df.columns else 0,
                }
                break
            except Exception as e:
                print(f"프로그램 {func_name} 오류: {e}")

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
        L.append("  데이터 없음 (pykrx 미지원)")
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
