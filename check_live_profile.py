import urllib.request

url = 'https://ai-ghn-gxt.up.railway.app/app.js'
js = urllib.request.urlopen(url).read().decode('utf-8')

print("=== CHECKING LIVE PRODUCTION APP.JS FOR PROFILE FIX ===")
print("Contains DEFAULT_25_KHOS:", 'DEFAULT_25_KHOS' in js)
print("Contains v=20260723-PROFILE-FIX:", 'PROFILE-FIX' in js)

# Search for setupProfileForm in live JS
lines = js.splitlines()
for i, line in enumerate(lines):
    if 'setupprofileform' in line.lower():
        print(f"Line {i+1}: {line[:100]}")
    if 'kho giao hàng nặng - đà nẵng' in line.lower():
        print(f"Line {i+1}: {line[:100]}")
