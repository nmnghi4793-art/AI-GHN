import sys, os, json, secrets
from datetime import datetime

sys.path.insert(0, '.')

from main import save_xe_van_hanh_records, import_xe_van_hanh_records, _load_xe_daily_records, _save_xe_daily_records, MASTER_30_XE_DAILY_RECORDS, XE_DAILY_META_FILE

# 1. Reset dataset to 30 master records
_save_xe_daily_records(MASTER_30_XE_DAILY_RECORDS, sync_db=False)
if os.path.exists(XE_DAILY_META_FILE):
    os.remove(XE_DAILY_META_FILE)

initial = _load_xe_daily_records()
print("1. Initial record count:", len(initial))
assert len(initial) == 30, f"Expected 30 records, got {len(initial)}"

# 2. Test manual save with exact Action #3 payload format:
# {
#   "date": "23/07/2026",
#   "warehouse": "Kho Giao Hàng Nặng - Tam Kỳ - Quảng Nam",
#   "recordType": "Xe tăng cường",
#   "vehicleCount": 1,
#   "licensePlate": "43C-123.55",
#   "vendor": "Thần Đèn",
#   "payloadKg": 1400
# }
class DummyRequest:
    def __init__(self, data):
        self._data = data
    async def json(self):
        return self._data

import asyncio
loop = asyncio.get_event_loop()

test_payload_1 = {
  "date": "23/07/2026",
  "warehouse": "Kho Giao Hàng Nặng - Tam Kỳ - Quảng Nam",
  "recordType": "Xe tăng cường",
  "vehicleCount": 1,
  "licensePlate": "43C-123.55",
  "vendor": "Thần Đèn",
  "payloadKg": 1400
}

res1 = loop.run_until_complete(save_xe_van_hanh_records(DummyRequest(test_payload_1)))
print("2. Save Record 1 Response:", json.dumps(res1, ensure_ascii=False))
assert res1["success"] is True, "Save 1 must return success: True"
assert res1["saved"] == 1, "Save 1 must save 1 record"

# 3. Test manual save with Xe OFF:
test_payload_2 = {
  "date": "23/07/2026",
  "warehouse": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa",
  "recordType": "Xe không hoạt động",
  "vehicleCount": 1,
  "licensePlate": "79H-888.88",
  "vendor": "Mạnh Cường",
  "payloadKg": 1900,
  "note": "Trễ ca"
}

res2 = loop.run_until_complete(save_xe_van_hanh_records(DummyRequest(test_payload_2)))
print("3. Save Record 2 Response:", json.dumps(res2, ensure_ascii=False))
assert res2["success"] is True, "Save 2 must return success: True"

recs_after = _load_xe_daily_records()
print("4. Active records count after manual saves:", len(recs_after))
assert len(recs_after) == 32, f"Expected 32, got {len(recs_after)}"

# Clean up
_save_xe_daily_records(MASTER_30_XE_DAILY_RECORDS, sync_db=False)
cleaned = _load_xe_daily_records()
print("5. Cleaned records count:", len(cleaned))
assert len(cleaned) == 30

print("\nALL PRODUCTION FIX TESTS PASSED 100%!")
