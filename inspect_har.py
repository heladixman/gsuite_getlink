import json
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

record_path = "CAPCUT 30D 7SEAT RECORD.json"
with open(record_path, "r", encoding="utf-8", errors="ignore") as f:
    data = json.load(f)

entries = data.get("log", {}).get("entries", [])
print(f"Total entries in HAR: {len(entries)}")

trade_entries = []
for idx, entry in enumerate(entries):
    req = entry.get("request", {})
    res = entry.get("response", {})
    url = req.get("url", "")
    if "init_trade" in url or "cashier" in url or "pipopay" in url:
        trade_entries.append((idx, entry))

print(f"Found {len(trade_entries)} matching entries for init_trade / cashier / pipopay:")
for idx, entry in trade_entries:
    req = entry.get("request", {})
    res = entry.get("response", {})
    url = req.get("url", "")
    method = req.get("method")
    status = res.get("status")
    print(f"\n==========================================")
    print(f"ENTRY [{idx}] -> {method} {status} {url}")
    
    # Request Headers & Body
    post_data = req.get("postData", {})
    if post_data:
        print("Request Payload:", post_data.get("text", "")[:500])
    
    # Response
    text = res.get("content", {}).get("text", "")
    print("Response Content:", text[:1500])
