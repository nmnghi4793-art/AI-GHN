import sys, os
sys.path.insert(0, '.')

from main import _load_xe_daily_records, _save_xe_daily_records

initial_recs = _load_xe_daily_records()
print("1. Initial record count:", len(initial_recs))

new_rec = {
    "id": "rec31_test",
    "ngay": "23/07/2026",
    "ten_kho": "Kho Giao Hàng Nặng - Hoà Xuân - Đà Nẵng",
    "loai": "Xe tăng cường",
    "so_luong_xe": 2,
    "bien_so_xe": "43C-313.13",
    "ten_ncc": "Bảo Châu Phát",
    "trong_tai": 2500,
    "ghi_chu": "Bản ghi thứ 31 thử nghiệm",
    "nguoi_nhap": "Tester",
    "thoi_gian_ghi_nhan": "2026-07-23T15:00:00Z"
}

initial_recs.append(new_rec)
_save_xe_daily_records(initial_recs, sync_db=False)

after_add = _load_xe_daily_records()
print("2. Record count after adding 31st record:", len(after_add))
assert len(after_add) == 31, f"Expected 31 records, got {len(after_add)}"

# Cleanup 31st record
after_add = [r for r in after_add if r.get("id") != "rec31_test"]
_save_xe_daily_records(after_add, sync_db=False)

final_recs = _load_xe_daily_records()
print("3. Record count after cleanup:", len(final_recs))
assert len(final_recs) == 30, f"Expected 30 records, got {len(final_recs)}"

print("TEST PASS 100%: Dynamic additions seamlessly scale from 30 to 31 records!")
