import json, sys

with open('scratch/xe_van_hanh_daily_backup.json', 'r', encoding='utf-8') as f:
    records = json.load(f)

print(f"Total backup records found: {len(records)}")
for i, r in enumerate(records):
    print(f"[{i+1}] ID:{r.get('id')} | Ngày:{r.get('ngay')} | Kho:{r.get('ten_kho')} | Loại:{r.get('loai')} | SL:{r.get('so_luong_xe')} | BSK:{r.get('bien_so_xe')} | NCC:{r.get('ten_ncc')}")
