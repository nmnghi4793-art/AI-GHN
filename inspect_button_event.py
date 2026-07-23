import urllib.request
import re

url_html = 'https://ai-ghn-gxt.up.railway.app/'
html = urllib.request.urlopen(url_html).read().decode('utf-8')

print("=== LIVE INDEX.HTML BUTTON & FORM INSPECTION ===")
for line in html.splitlines():
    if 'login-submit-btn' in line or 'login-form' in line or 'handleLoginSubmit' in line:
        print(line)

url_js = 'https://ai-ghn-gxt.up.railway.app/app.js?v=20260723-FORCE-999'
js = urllib.request.urlopen(url_js).read().decode('utf-8')

print("\n=== LIVE APP.JS HANDLELOGINSUBMIT INSPECTION ===")
matches = [l for l in js.splitlines() if 'handleloginsubmit' in l.lower()]
for m in matches[:10]:
    print(m)
