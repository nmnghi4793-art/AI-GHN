import urllib.request
import json

url = "https://ai-ghn-gxt.up.railway.app/api/bot/status"
print(f"Querying {url}...")
try:
    with urllib.request.urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("\n=== LIVE BOT STATUS ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error querying live status: {e}")
