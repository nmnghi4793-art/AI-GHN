import sys
import os
sys.path.insert(0, r'C:\Users\Admin\.gemini\antigravity-ide\scratch\ghn_odo_bot')
sys.stdout.reconfigure(encoding='utf-8')

from modules.calculator import (
    normalize_warehouse_name,
    build_warehouse_name_map,
    calculate_odo_status,
    WarehouseStatus,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_fleet(name, count, id_kho="K1"):
    return {"warehouseName": name, "warehouseId": id_kho, "activeVehicleCount": count}

def make_daily_inactive(name, count):
    return {"warehouseName": name, "inactiveVehicleCount": count, "additionalVehicleCount": 0}

def make_daily_additional(name, count):
    return {"warehouseName": name, "inactiveVehicleCount": 0, "additionalVehicleCount": count}

def run_calc(fleet, daily, odo_day, date_str="22/07/2026"):
    odo_data = {date_str: odo_day}
    fleet_names = [k["warehouseName"] for k in fleet]
    daily_names = [d["warehouseName"] for d in daily]
    odo_names = list(odo_day.keys())
    name_map = build_warehouse_name_map(fleet_names, odo_names, daily_names)
    return calculate_odo_status(date_str, fleet, daily, odo_data, name_map)

passed = 0
failed = 0

def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {msg}")
    else:
        failed += 1
        print(f"[FAIL] {msg}")

# TC1
fleet = [make_fleet("Kho Nha Trang", 9, "NT")]
daily = []
odo_day = {"Kho Nha Trang": {"51B-12345", "51B-23456", "51B-34567", "51B-45678", "51B-56789", "51B-67890"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.active_vehicles == 9 and s.expected_odo == 9 and s.reported_odo == 6 and s.missing_odo == 3, "TC1: Khong xe off/tang cuong")

# TC2
fleet = [make_fleet("Kho Nha Trang", 9, "NT")]
daily = [make_daily_inactive("Kho Nha Trang", 2)]
odo_day = {"Kho Nha Trang": {"51B-001", "51B-002", "51B-003", "51B-004", "51B-005", "51B-006"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.inactive_vehicles == 2 and s.expected_odo == 7 and s.missing_odo == 1, "TC2: Co xe off")

# TC3
fleet = [make_fleet("Kho Nha Trang", 9, "NT")]
daily = [make_daily_additional("Kho Nha Trang", 1)]
odo_day = {"Kho Nha Trang": {"51B-001", "51B-002", "51B-003", "51B-004", "51B-005", "51B-006"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.additional_vehicles == 1 and s.expected_odo == 10 and s.missing_odo == 4, "TC3: Co xe tang cuong")

# TC4
fleet = [make_fleet("Kho Nha Trang", 9, "NT")]
daily = [make_daily_inactive("Kho Nha Trang", 2), make_daily_additional("Kho Nha Trang", 1)]
odo_day = {"Kho Nha Trang": {"51B-001", "51B-002", "51B-003", "51B-004", "51B-005", "51B-006"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.expected_odo == 8 and s.missing_odo == 2, "TC4: Ca xe off va tang cuong (9-2+1=8)")

# TC5
fleet = [make_fleet("Kho Hoa Xuan", 5, "HX")]
daily = []
odo_day = {"Kho Hoa Xuan": {"51B-001", "51B-002", "51B-003", "51B-004", "51B-005"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.expected_odo == 5 and s.reported_odo == 5 and s.missing_odo == 0, "TC5: Da nhap du ODO")

# TC6
fleet = [make_fleet("Kho Quy Nhon", 8, "QN")]
daily = []
odo_day = {"Kho Quy Nhon": {"51B-001", "51B-002"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.missing_odo == 6, "TC6: Thieu ODO 1 ngay (8-2=6)")

# TC7 - Multiple days
fleet = [make_fleet("Kho Da Nang", 10, "DN")]
results_per_day = {}
for d, cnt in [("20/07/2026", 3), ("21/07/2026", 5), ("22/07/2026", 2)]:
    plates = {f"51B-{i:03d}" for i in range(cnt)}
    odo_data = {d: {"Kho Da Nang": plates}}
    nm = build_warehouse_name_map(["Kho Da Nang"], ["Kho Da Nang"], [])
    statuses = calculate_odo_status(d, fleet, [], odo_data, nm)
    results_per_day[d] = statuses[0].missing_odo
check(results_per_day["20/07/2026"] == 7 and results_per_day["21/07/2026"] == 5 and results_per_day["22/07/2026"] == 8,
      "TC7: Thieu ODO nhieu ngay (7,5,8)")

# TC8
fleet = [make_fleet("Kho Hue", 7, "HU")]
odo_21 = {"Kho Hue": {"51B-001", "51B-002", "51B-003"}}
r21 = run_calc(fleet, [], odo_21, date_str="21/07/2026")
odo_full = {"Kho Hue": {f"51B-{i:03d}" for i in range(7)}}
r22 = run_calc(fleet, [], odo_full, date_str="21/07/2026")
check(r21[0].missing_odo == 4 and r22[0].missing_odo == 0, "TC8: Bo sung du ODO ngay hom sau")

# TC9
odo_day = {"Kho Nha Trang": {"51B-001", "51B-001", "51B-002"}}
check(len(odo_day["Kho Nha Trang"]) == 2, "TC9: Dedup bien so trung")
fleet = [make_fleet("Kho Nha Trang", 5, "NT")]
r = run_calc(fleet, [], odo_day)
s = r[0]
check(s.reported_odo == 2 and s.missing_odo == 3, "TC9b: Dedup - tinh dung missing")

# TC10
fleet = [make_fleet("Kho Lien Chieu", 6, "LC")]
daily = []  # API loi tro ve empty
odo_day = {"Kho Lien Chieu": {"51B-001", "51B-002", "51B-003"}}
r = run_calc(fleet, daily, odo_day)
s = r[0]
check(s.inactive_vehicles == 0 and s.additional_vehicles == 0 and s.expected_odo == 6 and s.missing_odo == 3,
      "TC10: API Daily loi - xu ly graceful")

# Name normalization
fleet_names = ["Kho Giao Hang Nang - Nha Trang - Khanh Hoa"]
nm = build_warehouse_name_map(fleet_names, ["kho giao hang nang - nha trang - khanh hoa"], [])
check(nm.get("kho giao hang nang - nha trang - khanh hoa") is not None, "TC_EXTRA: Chuan hoa ten kho")

print(f"\n{'='*40}")
print(f"Ket qua: {passed} PASS, {failed} FAIL")
if failed == 0:
    print("ALL TESTS PASSED!")
