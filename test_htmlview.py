import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

url = "https://docs.google.com/spreadsheets/d/1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk/htmlview?gid=1962460963"

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8')
    
    print("HTML length:", len(html))
    
    # Save a slice of the HTML to inspect
    with open("c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/scratch/htmlview_output.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    # Search for some maps links in the HTML
    links = re.findall(r'href="(https?://[^"]+)"', html)
    print(f"Found {len(links)} total links in HTML.")
    
    maps_links = [l for l in links if 'maps' in l or 'google' in l or 'goo.gl' in l]
    print(f"Found {len(maps_links)} Google Maps links:")
    for l in maps_links[:10]:
        print("  -", l)
        
except Exception as e:
    print("Error:", str(e))
