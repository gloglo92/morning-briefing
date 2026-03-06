"""
퀀트 모닝 브리핑 텔레그램 봇
FinanceDataReader + KRX 직접 크롤링 버전
"""

import requests
from datetime import datetime, timedelta
import yfinance as yf
import traceback
import re

TELEGRAM_TOKEN = "8051338333:AAGzZAHrV4tGCRIO3UVRpzsdpUeHRqHESMs"
CHAT_ID = "311858790"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    return requests.post(url, json=payload).json()

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
                pct = (last_close - prev_close) / prev_close * 100
                result[name] = {"price": float(last_close), "pct": float(pct)}
        except Exception as e:
            print(f"{name} 오류: {e}")
            result[name] = None
    return result

def naver_investor(date_str, market="KOSPI"):
    """네이버 금융 투자자별 매매동향 크롤링"""
    mkt = "KOSPI" if market == "KOSPI" else "KOSDAQ"
    url = f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={date_str}&sosok={'0' if mkt=='KOSPI' else '1'}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'euc-kr'
        text = resp.text

        # 외국인/기관/개인 순매수 파싱
        # 네이버 금융 테이블에서 숫자 추출
        import re
        # 테이블 행에서 숫자 추출
        rows = re.findall(r'<td[^>]*class="[^"]*num[^"]*"[^>]*>([\-\+\d,]+)</td>', text)
        print(f"[{mkt}] 네이버 rows: {rows[:20]}")

        if len(rows) >= 3:
            def parse_num(s):
                s = s.replace(',', '').replace('+', '')
                return int(float(s) / 1e8) if s and s != '-' else 0
            return {
                "외국인": parse_num(rows[0]),
                "기관": parse_num(rows[1]),
                "개인": parse_num(rows[2]),
            }
    except Exception as e:
        print(f"네이버 {mkt} 오류: {e}")
    return None

def krx_investor_api(date_str, market="STK"):
    """KRX 정보데이터시스템 API - 세션 기반"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT02303.cmd",
        "Origin": "https://data.krx.co.kr",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })

    # 먼저 메인 페이지 접속 (세션 쿠키 획득)
    try:
        session.get("https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT02303.cmd", timeout=10)
    except:
        pass

    data = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02303",
        "locale": "ko_KR",
        "mktId": market,
        "trdDd": date_str,
        "money": "1",
        "askBid": "3",
        "share": "1",
        "part": "ALL",
        "cssId": "part1"
    }
    try:
        resp = session.post("https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
                           data=data, timeout=15)
        print(f"KRX {market} status: {resp.status_code}, len: {len(resp.text)}")
        if resp.text.strip():
            j = resp.json()
            rows = j.get("output", [])
            print(f"  rows: {len(rows)}, first keys: {list(rows[0].keys()) if rows else 'empty'}")
            result = {}
            for row in rows:
                inv = str(row.get("INVST_TP_NM", ""))
                val_str = str(row.get("NETBID_TRDVAL", "0")).replace(",", "")
                try: val = int(float(val_str) / 1e8)
                except: val = 0
                if "외국인" in inv and "기타" not in inv: result["외국인"] = val
                elif "기관합계" in inv or inv == "기관": result["기관"] = val
                elif inv == "개인": result["개인"] = val
            return result if result else None
    except Exception as e:
        print(f"KRX {market} 오류: {e}")
    return None

def fdr_investor(date_str, market="KOSPI"):
    """FinanceDataReader로 투자자별 매매동향"""
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(f"KRX/{market}/INVESTOR", date_str, date_str)
        print(f"FDR {market}: columns={list(df.columns)}, shape={df.shape}")
        print(df)
        if df is not None and len(df) > 0:
            row = df.iloc[-1]
            return {
                "외국인": int(row.get("외국인", row.get("Foreign", 0)) / 1e8),
                "기관": int(row.get("기관", row.get("Institution", 0)) / 1e8),
                "개인": int(row.get("개인", row.get("Individual", 0)) / 1e8),
            }
    except Exception as e:
        print(f"FDR {market} 오류: {e}")
    return None

def get_krx_data():
    date_str, date_label = get_prev_business_day()
    print(f"\n[KRX 조회 날짜: {date_str}]")
    result = {"date": date_label}

    # 방법1: KRX 세션 기반 API
    print("\n--- KRX API 시도 ---")
    result["kospi"] = krx_investor_api(date_str, "STK")
    if not result["kospi"]:
        # 방법2: FinanceDataReader
        print("\n--- FDR 시도 ---")
        result["kospi"] = fdr_investor(date_str, "KOSPI")
    if not result["kospi"]:
        # 방법3: 네이버 금융
        print("\n--- 네이버 금융 시도 ---")
        result["kospi"] = naver_investor(date_str, "KOSPI")

    result["kosdaq"] = krx_investor_api(date_str, "KSQ")
    if not result["kosdaq"]:
        result["kosdaq"] = fdr_investor(date_str, "KOSDAQ")
    if not result["kosdaq"]:
        result["kosdaq"] = naver_investor(date_str, "KOSDAQ")

    result["futures"] = None
    result["program"] = None
    return result

def arrow(pct):
    return "🔺" if pct > 0 else ("🔻" if pct < 0 else "➡️")

def fmt_val(val):
    if val is None: return "N/A"
    return f"{'+'if val>=0 else ''}{val:,}억"

def build_message(global_data, krx_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [f"📊 <b>퀀트 모닝 브리핑</b>", f"⏰ {now} 기준\n",
         "━━━━━━━━━━━━━━━━━━",
         "🌐 <b>글로벌 지표 (전일 미국 마감)</b>",
         "━━━━━━━━━━━━━━━━━━"]
    for name in ["나스닥", "S&P500", "다우존스"]:
        d = global_data.get(name)
        if d: L.append(f"{arrow(d['pct'])} {name}: <b>{d['price']:,.2f}</b> ({d['pct']:+.2f}%)")
        else: L.append(f"❓ {name}: 데이터 없음")
    L.append("")
    for name, label, fmt in [("VIX","VIX 공포지수","{:.2f}"),("브렌트유","브렌트유","${:.2f}"),("금","국제 금","${:,.2f}")]:
        d = global_data.get(name)
        if d: L.append(f"{arrow(d['pct'])} {label}: <b>{fmt.format(d['price'])}</b> ({d['pct']:+.2f}%)")
    L += ["", "━━━━━━━━━━━━━━━━━━",
          f"🇰🇷 <b>한국 증시 수급 ({krx_data['date']} 마감)</b>",
          "━━━━━━━━━━━━━━━━━━"]
    for label, key in [("코스피 현물","kospi"),("코스닥 현물","kosdaq")]:
        L.append(f"\n📌 <b>{label}</b>")
        d = krx_data.get(key)
        if d:
            L += [f"  외국인: {fmt_val(d.get('외국인'))}", f"  기관:   {fmt_val(d.get('기관'))}", f"  개인:   {fmt_val(d.get('개인'))}"]
        else: L.append("  데이터 없음")
    L.append(f"\n📌 <b>KOSPI200 선물</b>")
    d = krx_data.get("futures")
    if d: L += [f"  외국인: {fmt_val(d.get('외국인'))}", f"  기관:   {fmt_val(d.get('기관'))}", f"  개인:   {fmt_val(d.get('개인'))}"]
    else: L.append("  데이터 없음")
    L.append(f"\n📌 <b>코스피 프로그램 매매</b>")
    d = krx_data.get("program")
    if d: L += [f"  차익거래:   {fmt_val(d.get('차익'))}", f"  비차익거래: {fmt_val(d.get('비차익'))}", f"  전체:       {fmt_val(d.get('전체'))}"]
    else: L.append("  데이터 없음")
    L += ["\n━━━━━━━━━━━━━━━━━━", "Good morning! 오늘도 성공적인 매매 되세요 🙏"]
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
        error_msg = f"⚠️ 오류\n{traceback.format_exc()}"
        print(error_msg)
        send_telegram(error_msg)

if __name__ == "__main__":
    main()
