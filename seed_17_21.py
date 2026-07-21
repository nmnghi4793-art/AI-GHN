import os
import json
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_JSON = os.path.join(BASE_DIR, "xe_van_hanh_daily.json")
BACKUP_JSON = os.path.join(BASE_DIR, "xe_van_hanh_daily_backup.json")

warehouses = [
    ("Kho Giao Hàng Nặng - Đà Nẵng", "Đà Nẵng"),
    ("Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa", "Khánh Hòa"),
    ("Kho Giao Hàng Nặng - Vinh - Nghệ An", "Nghệ An"),
    ("Kho Giao Hàng Nặng - Quy Nhơn - Bình Định", "Bình Định"),
    ("Kho Giao Hàng Nặng - Đông Thọ -Thanh Hóa", "Thanh Hóa"),
    ("Kho Giao Hàng Nặng - Huế", "Thừa Thiên Huế"),
    ("Kho Giao Hàng Nặng - Phan Thiết - Bình Thuận", "Bình Thuận"),
    ("Kho Giao Hàng Nặng - Phan Rang - Ninh Thuận", "Ninh Thuận"),
    ("Kho Giao Hàng Nặng - Cam Ranh-Khánh Hòa", "Khánh Hòa"),
    ("Kho Giao Hàng Nặng - Thạch Linh - Hà Tĩnh", "Hà Tĩnh"),
    ("Kho Giao Hàng Nặng - Hội An - Quảng Nam", "Quảng Nam"),
    ("Kho Giao Hàng Nặng - Tuy Hòa - Phú Yên", "Phú Yên"),
    ("Kho Giao Hàng Nặng - Lagi - Bình Thuận", "Bình Thuận"),
]

ncc_list = ["Tín Thành", "Ngọc Đỉnh", "Mạnh Cường", "Gia Hân", "Bảo Châu Phát", "NAK"]
dates = ["17/07/2026", "18/07/2026", "19/07/2026", "20/07/2026", "21/07/2026"]

records = []

for idx, d in enumerate(dates):
    day_num = d[:2]
    # 4 Xe tăng cường per day
    tc_khos = [warehouses[(idx * 2 + i) % len(warehouses)] for i in range(4)]
    for i, (kho_full, prov) in enumerate(tc_khos):
        ncc = ncc_list[(idx + i) % len(ncc_list)]
        prefix = 43 if i == 0 else 79 if i == 1 else 37 if i == 2 else 77
        plate = f"{prefix}C-{(idx+1)*12+i*15:03d}.{(idx+5)*11:02d}"
        tt = 1900 if i % 2 == 0 else 2500 if i % 3 == 0 else 1400
        records.append({
            "id": secrets.token_hex(8),
            "ngay": d,
            "ten_kho": kho_full,
            "loai": "Xe tăng cường",
            "so_luong_xe": 1,
            "bien_so_xe": plate,
            "ten_ncc": ncc,
            "trong_tai": tt,
            "ghi_chu": "Tăng cường tải ca làm việc",
            "nguoi_nhap": "Điều hành Miền Trung",
            "thoi_gian_ghi_nhan": f"2026-07-{day_num}T08:30:00Z",
        })
    
    # 2 Xe không hoạt động per day
    off_khos = [warehouses[(idx * 2 + i + 5) % len(warehouses)] for i in range(2)]
    reasons = [
        ("Xe hư hỏng", "Hỏng hóc động cơ / thủng lốp"),
        ("Trễ giờ đến kho", "Tài xế trễ ca từ 7h30 - 9h30"),
        ("Xe bảo dưỡng", "Bảo dưỡng định kỳ theo lịch"),
        ("Nghỉ đột xuất", "Tài xế xin nghỉ đột xuất"),
    ]
    for i, (kho_full, prov) in enumerate(off_khos):
        ncc = ncc_list[(idx + i + 3) % len(ncc_list)]
        prefix = 79 if i == 0 else 36
        plate = f"{prefix}H-{(idx+3)*14+i*21:03d}.{(idx+2)*19:02d}"
        reason_title, reason_detail = reasons[(idx + i) % len(reasons)]
        records.append({
            "id": secrets.token_hex(8),
            "ngay": d,
            "ten_kho": kho_full,
            "loai": "Xe không hoạt động",
            "so_luong_xe": 1,
            "bien_so_xe": plate,
            "ten_ncc": ncc,
            "trong_tai": 1900,
            "ghi_chu": f"{reason_title}: {reason_detail}",
            "nguoi_nhap": "Điều hành Kho",
            "thoi_gian_ghi_nhan": f"2026-07-{day_num}T09:15:00Z",
        })

print(f"Generated {len(records)} records for 17/07/2026 - 21/07/2026.")

with open(MAIN_JSON, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

with open(BACKUP_JSON, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print("Saved main and backup JSON files successfully!")
