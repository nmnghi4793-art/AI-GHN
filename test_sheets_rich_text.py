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

try:
    if not os.path.exists(sa_path):
        print(f"Service account file {sa_path} not found")
        sys.exit(1)
        
    creds = Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build("sheets", "v4", credentials=creds)
    
    # Query sheet metadata and row data, specifying the fields we want to inspect
    result = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=["Kho Giao Hàng Nặng!A1:M30"],
        fields="sheets(data(rowData(values(hyperlink,formattedValue,userEnteredValue))))"
    ).execute()
    
    sheets = result.get("sheets", [])
    if sheets:
        data = sheets[0].get("data", [])
        if data:
            row_data = data[0].get("rowData", [])
            print("TOTAL ROWS:", len(row_data))
            
            # Print headers (row 0)
            headers = [col.get("formattedValue", "") for col in row_data[0].get("values", [])]
            print("HEADERS:", headers)
            
            # Find the index of column "Link GGM"
            link_idx = headers.index("Link GGM") if "Link GGM" in headers else -1
            print("LINK GGM INDEX:", link_idx)
            
            # Print rows details
            for i, row in enumerate(row_data[1:10]):
                values = row.get("values", [])
                ten_kho = values[4].get("formattedValue", "") if len(values) > 4 else ""
                
                # Check link column
                link_cell = values[link_idx] if len(values) > link_idx and link_idx != -1 else {}
                link_ggm = link_cell.get("hyperlink", "")
                
                # If hyperlink is not directly in the cell, maybe in formattedValue or userEnteredValue?
                # Sometimes it is inside textFormatRuns or userEnteredValue.
                print(f"Row {i+1}: Name={ten_kho}")
                print(f"  - hyperlink field: {repr(link_ggm)}")
                print(f"  - cell details: {json.dumps(link_cell, ensure_ascii=False)}")
                
except Exception as e:
    print("ERROR:", e)
