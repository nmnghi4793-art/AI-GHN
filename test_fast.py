import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

login_url = 'https://ai-ghn-gxt.up.railway.app/api/auth/login'
login_data = json.dumps({"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_data, headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
    res = json.loads(resp.read().decode('utf-8'))
    token = res.get('token')
    print(f"LOGIN 200 OK! Token: {token}")

meta_url = 'https://ai-ghn-gxt.up.railway.app/api/xe-van-hanh/meta'
req_meta = urllib.request.Request(meta_url, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req_meta, context=ctx, timeout=5) as r:
    data = r.read().decode('utf-8')
    print(f"META 200 OK! Data length: {len(data)} bytes")
