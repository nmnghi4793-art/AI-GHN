import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
SHEET_ID = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"

with open(os.path.join(BASE_DIR, "scratch", "xe_van_hanh_daily.json"), "r", encoding="utf-8") as f:
    records = json.load(f)

if os.path.exists(sa_path):
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        
        res = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        sheets = [s['properties']['title'] for s in res.get('sheets', [])]
        if "Xe Daily Logs" not in sheets:
            body = {
                "requests": [{
                    "addSheet": {
                        "properties": {"title": "Xe Daily Logs"}
                    }
                }]
            }
            service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
            print("Created tab 'Xe Daily Logs'")

        headers = [["ID", "Ngày", "Tên Kho", "Loại", "Số lượng xe", "Biển số xe", "Tên NCC", "Trọng tải", "Ghi chú", "Người nhập", "Thời gian ghi nhận"]]
        
        rows = []
        for r in records:
            rows.append([
                r.get("id", ""),
                r.get("ngay", ""),
                r.get("ten_kho", ""),
                r.get("loai", ""),
                str(r.get("so_luong_xe", 1)),
                r.get("bien_so_xe", ""),
                r.get("ten_ncc", ""),
                str(r.get("trong_tai", 1900)),
                r.get("ghi_chu", ""),
                r.get("nguoi_nhap", "Hệ thống"),
                r.get("thoi_gian_ghi_nhan", ""),
            ])

        # Overwrite full range
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID, range="Xe Daily Logs!A1:Z5000"
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Xe Daily Logs!A1",
            valueInputOption="USER_ENTERED",
            body={"values": headers + rows}
        ).execute()

        print(f"Successfully synced {len(rows)} records to Google Sheets 'Xe Daily Logs'!")
    except Exception as e:
        print("Sheets sync error:", e)
