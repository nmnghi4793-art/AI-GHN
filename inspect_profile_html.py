import urllib.request

url = 'https://ai-ghn-gxt.up.railway.app/'
html = urllib.request.urlopen(url).read().decode('utf-8')

print("=== CHECKING LIVE PROFILE HTML IN INDEX.HTML ===")
lines = html.splitlines()
for i, line in enumerate(lines):
    if 'profile-kho' in line.lower() or 'profile-submit-btn' in line.lower():
        print(f"Line {i+1}: {line.encode('ascii', 'ignore').decode('ascii')}")
