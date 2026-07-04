import urllib.request
import re
import urllib.parse
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

short_urls = [
    "https://maps.app.goo.gl/yiRWQXf7ngnrywg26",
    "https://maps.app.goo.gl/97i6GVsEzDZbBgtH7",
    "https://maps.app.goo.gl/QveGDzvMshKH8GVG6"
]

def get_coords_from_url(url):
    url = urllib.parse.unquote(url)
    # 1. @lat,lng
    m = re.search(r'@([-\d.]+),([-\d.]+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    # 2. !3dlat!4dlng
    m = re.search(r'!3d([-\d.]+)!4d([-\d.]+)', url)
    if m:
        return float(m.group(1)), float(m.group(2))
    # 3. general pattern: lat, +lng or lat, lng
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

for url in short_urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            final_url = response.geturl()
            coords = get_coords_from_url(final_url)
            print(f"Short URL: {url}")
            print(f"  -> Final URL: {final_url}")
            print(f"  -> Extracted Coords: {coords}")
    except Exception as e:
        print(f"Error for {url}: {e}")
