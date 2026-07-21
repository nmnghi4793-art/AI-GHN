import os
import json
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "xe_van_hanh_daily.json")
BACKUP_PATH = os.path.join(BASE_DIR, "xe_van_hanh_daily_backup.json")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    existing = json.load(f)

existing_keys = set((r["ngay"], r["ten_kho"].lower(), r["loai"], r["bien_so_xe"].lower()) for r in existing)

sample_entries = [
    # 17/07
    {"ngay": "17/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Đà Nẵng", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "43C-188.92", "ten_ncc": "Tín Thành", "trong_tai": 1900, "ghi_chu": "Xe tăng cường ca sáng", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "17/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa", "loai": "Xe không hoạt động", "so_luong_xe": 1, "bien_so_xe": "79H-021.45", "ten_ncc": "Mạnh Cường", "trong_tai": 1900, "ghi_chu": "Xe bảo dưỡng định kỳ", "nguoi_nhap": "Điều hành Kho"},
    
    # 18/07
    {"ngay": "18/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Vinh - Nghệ An", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "37H-091.33", "ten_ncc": "Ngọc Đỉnh", "trong_tai": 2500, "ghi_chu": "Tăng cường tải đỉnh điểm", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "18/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Quy Nhơn - Bình Định", "loai": "Xe không hoạt động", "so_luong_xe": 1, "bien_so_xe": "77C-054.12", "ten_ncc": "Gia Hân", "trong_tai": 1900, "ghi_chu": "Trễ giờ ca làm việc", "nguoi_nhap": "Điều hành Kho"},

    # 19/07
    {"ngay": "19/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Đông Thọ -Thanh Hóa", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "36H-022.41", "ten_ncc": "Ngọc Đỉnh", "trong_tai": 1900, "ghi_chu": "Tăng cường chạy giải tỏa backlog", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "19/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Đà Nẵng", "loai": "Xe không hoạt động", "so_luong_xe": 1, "bien_so_xe": "43C-099.15", "ten_ncc": "Tín Thành", "trong_tai": 1900, "ghi_chu": "Xe hỏng hóc lốp", "nguoi_nhap": "Điều hành Kho"},

    # 20/07
    {"ngay": "20/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Huế", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "75C-041.88", "ten_ncc": "Bảo Châu Phát", "trong_tai": 1900, "ghi_chu": "Xe tăng cường giao tuyến B2B", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "20/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Phan Thiết - Bình Thuận", "loai": "Xe không hoạt động", "so_luong_xe": 1, "bien_so_xe": "86H-012.34", "ten_ncc": "Mạnh Cường", "trong_tai": 1900, "ghi_chu": "Tài xế xin nghỉ đột xuất", "nguoi_nhap": "Điều hành Kho"},

    # 21/07 (Hôm nay)
    {"ngay": "21/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Đà Nẵng", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "43C-201.55", "ten_ncc": "Tín Thành", "trong_tai": 1900, "ghi_chu": "Tăng cường tải ca hôm nay", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "21/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa", "loai": "Xe tăng cường", "so_luong_xe": 1, "bien_so_xe": "79H-088.99", "ten_ncc": "Mạnh Cường", "trong_tai": 2500, "ghi_chu": "Tăng cường chạy đơn B2B", "nguoi_nhap": "Điều hành Kho"},
    {"ngay": "21/07/2026", "ten_kho": "Kho Giao Hàng Nặng - Vinh - Nghệ An", "loai": "Xe không hoạt động", "so_luong_xe": 1, "bien_so_xe": "37H-011.22", "ten_ncc": "Ngọc Đỉnh", "trong_tai": 1900, "ghi_chu": "Xe hỏng hóc động cơ", "nguoi_nhap": "Điều hành Kho"},
]

added_count = 0
for entry in sample_entries:
    key = (entry["ngay"], entry["ten_kho"].lower(), entry["loai"], entry["bien_so_xe"].lower())
    if key not in existing_keys:
        existing_keys.add(key)
        rec = dict(entry)
        rec["id"] = secrets.token_hex(8)
        day_str = entry["ngay"][:2]
        rec["thoi_gian_ghi_nhan"] = f"2026-07-{day_str}T08:30:00Z"
        existing.append(rec)
        added_count += 1

print(f"Added {added_count} new records for dates 17/07 - 21/07. Total records: {len(existing)}")

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

with open(BACKUP_PATH, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print("Updated JSON storage files successfully!")
