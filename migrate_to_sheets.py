import os, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(BASE_DIR)

backup_file = os.path.join(parent_dir, "scratch", "xe_van_hanh_daily_backup.json")
if not os.path.exists(backup_file):
    backup_file = os.path.join(BASE_DIR, "xe_van_hanh_daily_backup.json")

with open(backup_file, "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Loaded {len(records)} records from backup file.")

SHEET_ID = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"
sa_path = os.path.join(parent_dir, "alien-oarlock-499610-a5-2d813b6cc71d.json")

if not os.path.exists(sa_path):
    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")

print(f"SA path exists: {os.path.exists(sa_path)}")

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
        print("Existing sheets in Google Sheet:", sheets)

        if "Xe Daily Logs" not in sheets:
            body = {
                "requests": [{
                    "addSheet": {
                        "properties": {"title": "Xe Daily Logs"}
                    }
                }]
            }
            service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
            print("Created tab 'Xe Daily Logs'.")

        # Clear existing rows in Xe Daily Logs tab to do a fresh migration of 30 records
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range="Xe Daily Logs!A:K"
        ).execute()

        headers = [["ID", "Ngày", "Tên Kho", "Loại", "Số lượng xe", "Biển số xe", "Tên NCC", "Trọng tải", "Ghi chú", "Người nhập", "Thời gian ghi nhận"]]
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Xe Daily Logs!A1:K1",
            valueInputOption="RAW",
            body={"values": headers}
        ).execute()

        rows_to_append = []
        for r in records:
            rows_to_append.append([
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

        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="Xe Daily Logs!A2",
            valueInputOption="USER_ENTERED",
            body={"values": rows_to_append}
        ).execute()
        print(f"Successfully migrated {len(rows_to_append)} records to Google Sheets tab 'Xe Daily Logs'!")

    except Exception as e:
        print("Migration error:", e)
