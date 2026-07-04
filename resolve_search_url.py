import urllib.request
import re
import urllib.parse
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Row 3 URL from sheets
search_url = "https://www.google.com/maps?q=KC+H%C3%A0+T%C4%A9nh,+km09+%C4%90.+Tr%C3%A1nh+TP+H%C3%A0+T%C4%A9nh,+Th%E1%BA%A1ch+%C4%90%C3%A0i,+Th%E1%BA%A1ch+H%C3%A0,+H%C3%A0+T%C4%A9nh,+Vi%E1%BB%87t+Nam&ftid=0x313851588b892383:0x2a48263ac2063aef&entry=gps&shh=CAE&lucs=,94297699,94284499,94231188,94280568,47071704,94218641,94282134,94286869&g_ep=CAISEjI2LjExLjEuODgxMDA1NjQ2MBgAIIgnKkgsOTQyOTc2OTksOTQyODQ0OTksOTQyMzExODgsOTQyODA1NjgsNDcwNzE3MDQsOTQyMTg2NDEsOTQyODIxMzQsOTQyODY4NjlCAk1N&skid=ca93aff6-a7a5-4624-a62f-f78b8ca17f2a&g_st=iz"

def get_coords_from_url(url):
    url = urllib.parse.unquote(url)
    m = re.search(r'@([-\d.]+),([-\d.]+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'!3d([-\d.]+)!4d([-\d.]+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'([-\d\.]+),\s*\+?([-\d\.]+)', url)
    if m:
        try:
            lat = float(m.group(1))
            lng = float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
        except ValueError:
            pass
    return None

try:
    req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'})
    with urllib.request.urlopen(req, timeout=8) as response:
        final_url = response.geturl()
        coords = get_coords_from_url(final_url)
        print(f"Final URL: {final_url}")
        print(f"Coords: {coords}")
except Exception as e:
    print("ERROR:", e)
