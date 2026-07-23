import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

login_url = 'https://ai-ghn-gxt.up.railway.app/api/auth/login'
login_data = json.dumps({"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_data, headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req, context=ctx) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    token = res.get('token')
    print(f"Login success! Token: {token}")

endpoints = [
    'https://ai-ghn-gxt.up.railway.app/api/xe-van-hanh/meta',
    'https://ai-ghn-gxt.up.railway.app/api/kpi/gtc'
]

for ep in endpoints:
    req_ep = urllib.request.Request(ep, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req_ep, context=ctx) as r:
            data = r.read().decode('utf-8')
            print(f"[API 200 OK] {ep} => length: {len(data)} bytes")
    except urllib.error.HTTPError as e:
        print(f"[API ERR {e.code}] {ep} => {e.read().decode('utf-8', errors='ignore')}")
