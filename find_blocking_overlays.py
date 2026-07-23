import urllib.request
import re

url = 'https://ai-ghn-gxt.up.railway.app/'
html = urllib.request.urlopen(url).read().decode('utf-8')

print("=== CHECKING ALL FIXED / ABSOLUTE OVERLAYS IN INDEX.HTML ===")

lines = html.splitlines()
for i, line in enumerate(lines):
    if 'position: fixed' in line.lower() or 'position:fixed' in line.lower() or 'overlay' in line.lower() or 'modal' in line.lower() or 'z-index' in line.lower():
        print(f"Line {i+1}: {line.encode('ascii', 'ignore').decode('ascii')[:120]}")
