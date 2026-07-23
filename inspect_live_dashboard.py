import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 1. Check live app.js for nextSyncTime in finally
url_js = 'https://ai-ghn-gxt.up.railway.app/app.js'
js = urllib.request.urlopen(url_js).read().decode('utf-8')

print("=== CHECKING LIVE PRODUCTION APP.JS ===")
print("Contains PERF-FIX in version tag:", 'PERF-FIX' in js)
print("Contains nextSyncTime in finally:", 'LUÔN CẬP NHẬT THỜI GIAN ĐỒNG BỘ' in js or 'nextSyncTime = Date.now() + 5 * 60 * 1000;' in js)

# Find loadDashboardFromCache in live JS
pos = js.find('async function loadDashboardFromCache')
if pos != -1:
    print("\n--- Live loadDashboardFromCache snippet ---")
    print(js[pos:pos+1200])
