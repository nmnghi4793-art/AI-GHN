import urllib.request
import json
import time
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url_login = 'https://ai-ghn-gxt.up.railway.app/api/auth/login'
payload = json.dumps({"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"}).encode('utf-8')
req = urllib.request.Request(url_login, data=payload, headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req, context=ctx) as r:
    token = json.loads(r.read().decode('utf-8'))['token']

url_cache = 'https://ai-ghn-gxt.up.railway.app/api/dashboard-cache'
t0 = time.time()
req_c = urllib.request.Request(url_cache, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req_c, context=ctx) as r:
    data = json.loads(r.read().decode('utf-8'))
    t1 = time.time()
    print(f"=== PRODUCTION MEASUREMENT RESULT ===")
    print(f"HTTP Status: {r.status}")
    print(f"Response Time: {t1-t0:.2f} seconds")
    print(f"Payload Size: {len(json.dumps(data))/1024:.2f} KB")
