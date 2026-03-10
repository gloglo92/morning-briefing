import requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import traceback

TELEGRAM_TOKEN = “8051338333:AAGzZAHrV4tGCRIO3UVRpzsdpUeHRqHESMs”
CHAT_ID = “311858790”
KST = timezone(timedelta(hours=9))

def send_telegram(message):
url = “https://api.telegram.org/bot” + TELEGRAM_TOKEN + “/sendMessage”
payload = {“chat_id”: CHAT_ID, “text”: message, “parse_mode”: “HTML”}
return requests.post(url, json=payload).json()

def get_global_data():
tickers = {
“나스닥”: “^IXIC”,
“S&P500”: “^GSPC”,
“다우존스”: “^DJI”,
“VIX”: “^VIX”,
“브렌트유”: “BZ=F”,
“금”: “GC=F”,
“원달러”: “KRW=X”,
}
result = {}
for name, ticker in tickers.items():
try:
df = yf.Ticker(ticker).history(period=“10d”)
df = df[df[“Close”] > 0].dropna(subset=[“Close”])
if len(df) >= 2:
prev = float(df[“Close”].iloc[-2])
last = float(df[“Close”].iloc[-1])
pct = (last - prev) / prev * 100
result[name] = {“price”: last, “pct”: pct}
else:
result[name] = None
except Exception as e:
print(name + “ 오류: “ + str(e))
result[name] = None
return result

def arrow(pct):
if pct > 0:
return “🔺”
elif pct < 0:
return “🔻”
else:
return “➡️”

def build_message(data):
now = datetime.now(KST).strftime(”%Y-%m-%d %H:%M KST”)
L = []
L.append(“📊 <b>퀀트 모닝 브리핑</b>”)
L.append(“⏰ “ + now + “\n”)
L.append(“━━━━━━━━━━━━━━━━━━”)
L.append(“🌐 <b>미국 증시 (전일 마감)</b>”)
L.append(“━━━━━━━━━━━━━━━━━━”)
for name in [“나스닥”, “S&P500”, “다우존스”]:
d = data.get(name)
if d:
L.append(arrow(d[“pct”]) + “ “ + name + “: <b>” + “{:,.2f}”.format(d[“price”]) + “</b> (” + “{:+.2f}”.format(d[“pct”]) + “%)”)
else:
L.append(“❓ “ + name + “: 데이터 없음”)
L.append(””)
L.append(“━━━━━━━━━━━━━━━━━━”)
L.append(“📈 <b>글로벌 매크로</b>”)
L.append(“━━━━━━━━━━━━━━━━━━”)
macros = [
(“원달러”, “원/달러 환율”, “{:,.2f}원”),
(“VIX”, “VIX 공포지수”, “{:.2f}”),
(“브렌트유”, “브렌트유”, “${:.2f}”),
(“금”, “국제 금”, “${:,.2f}”),
]
for name, label, fmt in macros:
d = data.get(name)
if d:
L.append(arrow(d[“pct”]) + “ “ + label + “: <b>” + fmt.format(d[“price”]) + “</b> (” + “{:+.2f}”.format(d[“pct”]) + “%)”)
L.append(””)
L.append(“━━━━━━━━━━━━━━━━━━”)
L.append(“Good morning! 오늘도 성공적인 매매 되세요 🙏”)
return “\n”.join(L)

def main():
try:
print(“데이터 수집 중…”)
data = get_global_data()
message = build_message(data)
print(message)
result = send_telegram(message)
if result.get(“ok”):
print(“발송 완료!”)
else:
print(“실패: “ + str(result))
except Exception as e:
error_msg = “오류 발생\n” + traceback.format_exc()
print(error_msg)
send_telegram(error_msg)

if **name** == “**main**”:
main()
