import os
import json
import sys
import io
import re
import urllib.request
import urllib.parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sa_path = "alien-oarlock-499610-a5-2d813b6cc71d.json"
spreadsheet_id = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"

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

def resolve_url(url):
    if not url:
        return None
    if "maps.app.goo.gl" in url or "goo.gl/maps" in url:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.geturl()
        except Exception as e:
            print(f"Error resolving {url}: {e}")
            return url
    return url

try:
    creds = Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build("sheets", "v4", credentials=creds)
    
    result = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=["Kho Giao Hàng Nặng!A1:M100"],
        fields="sheets(data(rowData(values(hyperlink,formattedValue))))"
    ).execute()
    
    sheets = result.get("sheets", [])
    if sheets:
        data = sheets[0].get("data", [])
        if data:
            row_data = data[0].get("rowData", [])
            headers = [col.get("formattedValue", "") for col in row_data[0].get("values", [])]
            link_idx = headers.index("Link GGM") if "Link GGM" in headers else -1
            
            resolved_count = 0
            for i, row in enumerate(row_data[1:]):
                values = row.get("values", [])
                if not values:
                    continue
                id_kho = values[0].get("formattedValue", "") if len(values) > 0 else ""
                ten_kho = values[4].get("formattedValue", "") if len(values) > 4 else ""
                
                link_cell = values[link_idx] if len(values) > link_idx and link_idx != -1 else {}
                link_ggm = link_cell.get("hyperlink", "")
                
                # Resolve and parse
                final_url = resolve_url(link_ggm)
                coords = get_coords_from_url(final_url) if final_url else None
                
                status = "RESOLVED" if coords else "FAILED"
                if coords:
                    resolved_count += 1
                print(f"Row {i+1}: ID={id_kho}, Name={ten_kho}")
                print(f"  - Link: {link_ggm}")
                print(f"  - Status: {status} | Coords: {coords}")
            print(f"\nSUCCESSFULLY RESOLVED {resolved_count}/{len(row_data)-1} WAREHOUSES")
            
except Exception as e:
    print("ERROR:", e)
