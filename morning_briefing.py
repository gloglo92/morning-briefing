"""
퀀트 모닝 브리핑 텔레그램 봇
매일 오전 7시 자동 발송
"""

import requests
from datetime import datetime, timedelta
import yfinance as yf
from pykrx import stock
import traceback

# ==========================================
# 설정값
# ==========================================
TELEGRAM_TOKEN = "8051338333:AAGzZAHrV4tGCRIO3UVRpzsdpUeHRqHESMs"
CHAT_ID = "311858790"

# ==========================================
# 텔레그램 메시지 발송
# ==========================================
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    return response.json()

# ==========================================
# 1) 글로벌 지표 수집 (yfinance)
# ==========================================
def get_global_data():
    tickers = {
        "나스닥":   "^IXIC",
        "S&P500":  "^GSPC",
        "다우존스": "^DJI",
        "VIX":     "^VIX",
        "브렌트유": "BZ=F",
        "금":       "GC=F",
    }

    result = {}
    for name, ticker in tickers.items():
        try:
            df = yf.Ticker(ticker).history(period="5d")
            if len(df) >= 2:
                prev_close = df['Close'].iloc[-2]
                last_close = df['Close'].iloc[-1]
                change = last_close - prev_close
                pct    = (change / prev_close) * 100
                result[name] = {
                    "price": last_close,
                    "change": change,
                    "pct": pct
                }
        except Exception:
            result[name] = None
    return result

# ==========================================
# 2) 한국 증시 수급 (pykrx)
# ==========================================
def get_krx_data():
    # 전날 날짜 (주말이면 금요일로 자동 조정)
    today = datetime.today()
    target = today - timedelta(days=1)
    # 월요일(0)이면 금요일로
    if target.weekday() == 6:  # 일요일
        target -= timedelta(days=2)
    elif target.weekday() == 5:  # 토요일
        target -= timedelta(days=1)
    date_str = target.strftime("%Y%m%d")

    result = {"date": target.strftime("%Y-%m-%d"), "date_str": date_str}

    try:
        # 코스피 투자자별 순매수
        kospi = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSPI")
        result["kospi"] = {
            "외국인": int(kospi.loc["외국인합계", "순매수"] / 1e8) if "외국인합계" in kospi.index else 0,
            "기관":   int(kospi.loc["기관합계",   "순매수"] / 1e8) if "기관합계"   in kospi.index else 0,
            "개인":   int(kospi.loc["개인",       "순매수"] / 1e8) if "개인"       in kospi.index else 0,
        }
    except Exception:
        result["kospi"] = None

    try:
        # 코스닥 투자자별 순매수
        kosdaq = stock.get_market_trading_value_by_investor(date_str, date_str, "KOSDAQ")
        result["kosdaq"] = {
            "외국인": int(kosdaq.loc["외국인합계", "순매수"] / 1e8) if "외국인합계" in kosdaq.index else 0,
            "기관":   int(kosdaq.loc["기관합계",   "순매수"] / 1e8) if "기관합계"   in kosdaq.index else 0,
            "개인":   int(kosdaq.loc["개인",       "순매수"] / 1e8) if "개인"       in kosdaq.index else 0,
        }
    except Exception:
        result["kosdaq"] = None

    try:
        # 선물 투자자별 순매수
        futures = stock.get_futures_trading_value_by_investor(date_str, date_str, "KOSPI200")
        result["futures"] = {
            "외국인": int(futures.loc["외국인합계", "순매수"] / 1e8) if "외국인합계" in futures.index else 0,
            "기관":   int(futures.loc["기관합계",   "순매수"] / 1e8) if "기관합계"   in futures.index else 0,
            "개인":   int(futures.loc["개인",       "순매수"] / 1e8) if "개인"       in futures.index else 0,
        }
    except Exception:
        result["futures"] = None

    try:
        # 프로그램 매매 동향 (차익/비차익)
        prog = stock.get_program_trading_trend(date_str, date_str)
        result["program"] = {
            "차익":   int(prog["차익"].iloc[-1]   / 1e8) if "차익"   in prog.columns else 0,
            "비차익": int(prog["비차익"].iloc[-1] / 1e8) if "비차익" in prog.columns else 0,
            "전체":   int(prog["전체"].iloc[-1]   / 1e8) if "전체"   in prog.columns else 0,
        }
    except Exception:
        result["program"] = None

    return result

# ==========================================
# 3) 메시지 포맷 생성
# ==========================================
def arrow(pct):
    if pct > 0:
        return "🔺"
    elif pct < 0:
        return "🔻"
    else:
        return "➡️"

def fmt_krw(val):
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:,}억"

def build_message(global_data, krx_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"📊 <b>퀀트 모닝 브리핑</b>")
    lines.append(f"⏰ {now} 기준\n")

    # ── 글로벌 지표 ──
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 <b>글로벌 지표 (전일 미국 마감)</b>")
    lines.append("━━━━━━━━━━━━━━━━━━")

    indices = ["나스닥", "S&P500", "다우존스"]
    for name in indices:
        d = global_data.get(name)
        if d:
            em = arrow(d['pct'])
            lines.append(f"{em} {name}: <b>{d['price']:,.2f}</b> ({d['pct']:+.2f}%)")
        else:
            lines.append(f"❓ {name}: 데이터 없음")

    lines.append("")

    # VIX
    d = global_data.get("VIX")
    if d:
        em = arrow(d['pct'])
        lines.append(f"{em} VIX 공포지수: <b>{d['price']:.2f}</b> ({d['pct']:+.2f}%)")

    # 브렌트유
    d = global_data.get("브렌트유")
    if d:
        em = arrow(d['pct'])
        lines.append(f"{em} 브렌트유: <b>${d['price']:.2f}</b> ({d['pct']:+.2f}%)")

    # 금
    d = global_data.get("금")
    if d:
        em = arrow(d['pct'])
        lines.append(f"{em} 국제 금: <b>${d['price']:,.2f}</b> ({d['pct']:+.2f}%)")

    # ── 한국 증시 수급 ──
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"🇰🇷 <b>한국 증시 수급 ({krx_data['date']} 마감)</b>")
    lines.append("━━━━━━━━━━━━━━━━━━")

    # 코스피
    lines.append("\n📌 <b>코스피 현물</b>")
    if krx_data.get("kospi"):
        k = krx_data["kospi"]
        lines.append(f"  외국인: {fmt_krw(k['외국인'])}")
        lines.append(f"  기관:   {fmt_krw(k['기관'])}")
        lines.append(f"  개인:   {fmt_krw(k['개인'])}")
    else:
        lines.append("  데이터 없음")

    # 코스닥
    lines.append("\n📌 <b>코스닥 현물</b>")
    if krx_data.get("kosdaq"):
        k = krx_data["kosdaq"]
        lines.append(f"  외국인: {fmt_krw(k['외국인'])}")
        lines.append(f"  기관:   {fmt_krw(k['기관'])}")
        lines.append(f"  개인:   {fmt_krw(k['개인'])}")
    else:
        lines.append("  데이터 없음")

    # 선물
    lines.append("\n📌 <b>KOSPI200 선물</b>")
    if krx_data.get("futures"):
        f = krx_data["futures"]
        lines.append(f"  외국인: {fmt_krw(f['외국인'])}")
        lines.append(f"  기관:   {fmt_krw(f['기관'])}")
        lines.append(f"  개인:   {fmt_krw(f['개인'])}")
    else:
        lines.append("  데이터 없음")

    # 프로그램 매매
    lines.append("\n📌 <b>코스피 프로그램 매매</b>")
    if krx_data.get("program"):
        p = krx_data["program"]
        lines.append(f"  차익거래:   {fmt_krw(p['차익'])}")
        lines.append(f"  비차익거래: {fmt_krw(p['비차익'])}")
        lines.append(f"  전체:       {fmt_krw(p['전체'])}")
    else:
        lines.append("  데이터 없음")

    lines.append("\n━━━━━━━━━━━━━━━━━━")
    lines.append("Good morning! 오늘도 성공적인 매매 되세요 🙏")

    return "\n".join(lines)

# ==========================================
# 메인 실행
# ==========================================
def main():
    try:
        print("📡 글로벌 데이터 수집 중...")
        global_data = get_global_data()

        print("📡 한국 증시 수급 수집 중...")
        krx_data = get_krx_data()

        print("📝 메시지 생성 중...")
        message = build_message(global_data, krx_data)

        print("📨 텔레그램 발송 중...")
        result = send_telegram(message)

        if result.get("ok"):
            print("✅ 발송 완료!")
        else:
            print(f"❌ 발송 실패: {result}")

    except Exception as e:
        error_msg = f"⚠️ 브리핑 오류 발생\n{traceback.format_exc()}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    main()
