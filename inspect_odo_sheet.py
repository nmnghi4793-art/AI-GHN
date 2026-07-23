import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')
from main import BASE_DIR

sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
with open(sa_path, "r", encoding="utf-8") as f:
    sa_info = json.load(f)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_file(sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
service = build("sheets", "v4", credentials=creds)

ODO_SHEET_ID = "1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo"

meta = service.spreadsheets().get(spreadsheetId=ODO_SHEET_ID).execute()
sheet_titles = [s['properties']['title'] for s in meta.get('sheets', [])]

print("All Tab Titles in ODO Sheet:", sheet_titles)

target_tab = None
for title in sheet_titles:
    if "Tháng 7" in title or "THÁNG 7" in title or "Thang 7" in title:
        target_tab = title
        break

if not target_tab:
    target_tab = sheet_titles[0]

print(f"\nTarget Tab Selected: '{target_tab}'")

# Fetch all rows with range 'Tháng 7'!A:Z
range_name = f"'{target_tab}'!A:Z"
res = service.spreadsheets().values().get(spreadsheetId=ODO_SHEET_ID, range=range_name).execute()
rows = res.get("values", [])

print(f"Total rows fetched from '{target_tab}': {len(rows)}")

if len(rows) > 0:
    print("Header Row 1:", rows[0][:10])

# Inspect last 10 rows
print("\nLast 10 rows:")
for r in rows[-10:]:
    col_a = r[0] if len(r) > 0 else ""
    col_f = r[5] if len(r) > 5 else ""
    col_h = r[7] if len(r) > 7 else ""
    print(f"Col A (Time): {col_a} | Col F (Kho): {col_f} | Col H (Biển): {col_h}")
