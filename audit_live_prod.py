import urllib.request
import json

url_html = 'https://ai-ghn-gxt.up.railway.app/'
url_js = 'https://ai-ghn-gxt.up.railway.app/app.js?v=20260723-AUTOSTART-LIVE'

print("=== AUDITING LIVE PRODUCTION RAILWAY FRONTEND SERVING ===")

# 1. Fetch HTML and check script tags & headers
with urllib.request.urlopen(url_html) as resp:
    html_headers = resp.headers
    html = resp.read().decode('utf-8')
    print(f"HTML HTTP Status: {resp.status}")
    print(f"HTML Content-Type: {html_headers.get('Content-Type')}")

# Find script tags in HTML
for line in html.splitlines():
    if '<script' in line.lower():
        print(f"Script tag in HTML: {line.strip()}")

# 2. Fetch JS and check headers & content
req_js = urllib.request.Request(url_js)
with urllib.request.urlopen(req_js) as resp:
    js_headers = resp.headers
    js = resp.read().decode('utf-8')
    print(f"\nJS HTTP Status: {resp.status}")
    print(f"JS Content-Type: {js_headers.get('Content-Type')}")
    print(f"JS Length: {len(js)} bytes")
    print(f"JS First 100 chars: {js[:100]!r}")
    print(f"JS Contains AUTOSTART-LIVE: {'AUTOSTART-LIVE' in js or 'autoStartDashboard' in js}")

# 3. Check backend main.py serve logic
print("\n=== CHECKING FRONTEND SERVE PATH IN MAIN.PY ===")
with open('main.py', 'r', encoding='utf-8') as f:
    main_py = f.read()

for line in main_py.splitlines():
    if 'FRONTEND_DIR' in line or 'StaticFiles' in line or 'mount' in line:
        print(line)
