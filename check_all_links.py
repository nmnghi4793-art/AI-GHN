import urllib.request
import csv
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    url = "https://docs.google.com/spreadsheets/d/1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk/export?format=csv&gid=1962460963"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        for i, row in enumerate(reader):
            print(f"Row {i+1}: ID={row.get('ID Kho')}, Name={row.get('Tên Kho GXT')}, Link={row.get('Link GGM')}")
except Exception as e:
    print("ERROR:", e)
