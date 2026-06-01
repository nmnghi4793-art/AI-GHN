import urllib.request
import csv
import io
import json

try:
    url = "https://docs.google.com/spreadsheets/d/1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk/export?format=csv&gid=541379955"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        info = {
            "total_rows": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "sample": rows[0] if rows else {}
        }
        with open("xe_gxt_info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    print("SUCCESS")
except Exception as e:
    with open("xe_gxt_info.json", "w", encoding="utf-8") as f:
        json.dump({"error": str(e)}, f, ensure_ascii=False, indent=2)
    print("ERROR:", e)
