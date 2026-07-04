import os
import json
import sys
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Path to service account file
sa_path = "alien-oarlock-499610-a5-2d813b6cc71d.json"
spreadsheet_id = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"
sheet_range = "Kho Giao Hàng Nặng!A:M"

try:
    if not os.path.exists(sa_path):
        print(f"Service account file {sa_path} not found")
        sys.exit(1)
        
    creds = Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build("sheets", "v4", credentials=creds)
    
    # Get values with FORMULA option to retrieve hyperlink formulas
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_range,
        valueRenderOption="FORMULA"
    ).execute()
    
    values = result.get("values", [])
    print("TOTAL ROWS FETCHED:", len(values))
    if values:
        headers = values[0]
        print("HEADERS:", headers)
        
        # Print first 5 rows with formulas
        for i, row in enumerate(values[1:6]):
            # Fill missing columns
            while len(row) < len(headers):
                row.append("")
            # Print columns of interest
            id_kho = row[headers.index("ID Kho")] if "ID Kho" in headers else "N/A"
            ten_kho = row[headers.index("Tên Kho GXT")] if "Tên Kho GXT" in headers else "N/A"
            link = row[headers.index("Link GGM")] if "Link GGM" in headers else "N/A"
            dia_chi = row[headers.index("Địa chỉ kho")] if "Địa chỉ kho" in headers else "N/A"
            print(f"Row {i+1}: ID={id_kho}, Name={ten_kho}, Address={dia_chi[:30]}..., LinkFormula={link}")
    else:
        print("NO VALUES RETURNED")
        
except Exception as e:
    print("ERROR:", e)
