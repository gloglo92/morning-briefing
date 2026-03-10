

import requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import traceback

TELEGRAM_TOKEN = “8051338333:AAGzZAHrV4tGCRIO3UVRpzsdpUeHRqHESMs”
CHAT_ID = “311858790”

KST = timezone(timedelta(hours=9))

def send_telegram(message: str):
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”
payload = {“chat_id”: CHAT_ID, “text”: message, “parse_mode”: “HTML”}
return requests.post(url, json=payload).json()

def get_global_data():
tickers = {
“나스닥”:   “^IXIC”,
“S&P500”:  “^GSPC”,
“다우존스”: “^DJI”,
“VIX”:     “^VIX”,
“브렌트유”: “BZ=F”,
“금”:       “GC=F”,
“원달러”:   “KRW=X”,
}
result = {}
for name, ticker in tickers.items():
try:
df = yf.Ticker(ticker).history(period=“10d”)
# 거래일 데이터만 (종가가 0이 아닌 행)
df = df[df[‘Close’] > 0].dropna(subset=[‘Close’])
if len(df) >= 2:
prev = float(df[‘Close’].iloc[-2])
last = float(df[‘Close’].iloc[-1])
pct  = (last - prev) / prev * 100
result[name] = {“price”: last, “pct”: pct}
else:
result[name] = None
except Exception as e:
print(f”{name} 오류: {e}”)
result[name] = None
return result

def arrow(pct):
return “🔺” if pct > 0 else (“🔻” if pct < 0 else “➡️”)

def build_message(data):
now = datetime.now(KST).strftime(”%Y-%m-%d %H:%M KST”)
L = []
L.append(“📊 <b>퀀트 모닝 브리핑</b>”)
L.append(f”⏰ {now}\n”)
L.append(“━━━━━━━━━━━━━━━━━━”)
L.append(“🌐 <b>미국 증시 (전일 마감)</b>”)
L.append(“━━━━━━━━━━━━━━━━━━”)

```
for name in ["나스닥", "S&P500", "다우존스"]:
    d = data.get(name)
    if d:
        L.append(f"{arrow(d['pct'])} {name}: <b>{d['price']:,.2f}</b> ({d['pct']:+.2f}%)")
    else:
        L.append(f"❓ {name}: 데이터 없음")

L.append("")
L.append("━━━━━━━━━━━━━━━━━━")
L.append("📈 <b>글로벌 매크로</b>")
L.append("━━━━━━━━━━━━━━━━━━")

for name, label, fmt in [
    ("원달러",   "원/달러 환율", "{:,.2f}원"),
    ("VIX",     "VIX 공포지수", "{:.2f}"),
    ("브렌트유", "브렌트유",     "${:.2f}"),
    ("금",       "국제 금",      "${:,.2f}"),
]:
    d = data.get(name)
    if d:
        L.append(f"{arrow(d['pct'])} {label}: <b>{fmt.format(d['price'])}</b> ({d['pct']:+.2f}%)")

L.append("")
L.append("━━━━━━━━━━━━━━━━━━")
L.append("Good morning! 오늘도 성공적인 매매 되세요 🙏")
return "\n".join(L)
```

def main():
try:
print(“📡 글로벌 데이터 수집 중…”)
data = get_global_data()
message = build_message(data)
print(message)
result = send_telegram(message)
print(“✅ 발송 완료!” if result.get(“ok”) else f”❌ 실패: {result}”)
except Exception as e:
error_msg = f”⚠️ 오류\n{traceback.format_exc()}”
print(error_msg)
send_telegram(error_msg)

if **name** == “**main**”:
main()
