import urllib.request
import csv
import io
import json
import sys

# Set output to utf-8 for terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    url = "https://docs.google.com/spreadsheets/d/1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk/export?format=csv&gid=1962460963"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        print("TOTAL ROWS:", len(rows))
        if rows:
            print("COLUMNS:")
            for k in rows[0].keys():
                print(f"  - {repr(k)}")
            print("SAMPLE ROW:")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2))
        else:
            print("NO ROWS FOUND")
except Exception as e:
    print("ERROR:", e)
