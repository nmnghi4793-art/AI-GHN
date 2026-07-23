import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://ai-ghn-gxt.up.railway.app/api/auth/login'
test_cases = [
    {"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"},
    {"username": "GIAOHANGNANGMIENTRUNG", "password": "GXT@MienTrung2026!"},
    {"username": "admin", "password": "admin"}
]

for tc in test_cases:
    data = json.dumps(tc).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            body = response.read().decode('utf-8')
            print(f"[200 OK] user='{tc['username']}' => body: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"[{e.code}] user='{tc['username']}' => body: {body}")
    except Exception as e:
        print(f"[ERR] user='{tc['username']}' => {e}")
