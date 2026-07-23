import os
import sys
import time
import ssl
import json
import secrets
from datetime import datetime, timedelta, date
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import main

# GO-LIVE EXACT TIMESTAMP: 23/07/2026 18:00:00 (Asia/Ho_Chi_Minh)
GOLIVE_DATETIME = datetime(2026, 7, 23, 18, 0, 0)
GOLIVE_DATE = date(2026, 7, 23)

ODO_SHEET_ID = os.environ.get("ODO_SHEET_ID", "1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo")
CACHE_FILE = os.path.join(BASE_DIR, "scratch", "odo_cache.json")
LOGS_FILE = os.path.join(BASE_DIR, "scratch", "odo_monitor_logs.json")

_ODO_CACHE = {
    "timestamp": 0,
    "data": {}
}

CACHE_TTL_SECONDS = 180  # 3 minutes cache TTL

def get_vn_datetime() -> datetime:
    """Trả về datetime theo múi giờ Việt Nam (Asia/Ho_Chi_Minh / UTC+7)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=7)

def is_before_golive(date_str: str = None) -> bool:
    """
    Kiểm tra xem mốc thời gian kiểm tra có trước thời điểm GO-LIVE (18:00 23/07/2026) hay không.
    - Ngày < 23/07/2026 -> True (Trước Go-Live)
    - Ngày 23/07/2026 trước 18:00 -> True (Trước Go-Live)
    - Ngày 23/07/2026 từ 18:00 trở đi -> False (GO-LIVE DÃ KÍCH HOẠT)
    - Ngày > 23/07/2026 -> False (GO-LIVE ĐÃ KÍCH HOẠT)
    """
    vn_now = get_vn_datetime()
    vn_now_naive = vn_now.replace(tzinfo=None) if vn_now.tzinfo else vn_now

    if not date_str:
        return vn_now_naive < GOLIVE_DATETIME

    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            target_d = date(y, m, d)
            if target_d < GOLIVE_DATE:
                return True
            elif target_d == GOLIVE_DATE:
                return vn_now_naive < GOLIVE_DATETIME
            else:
                return False
    except Exception:
        pass
    return False

def parse_odo_date(raw_val) -> str:
    """
    Hỗ trợ đọc và chuyển đổi mọi định dạng ngày từ Google Sheets về chuỗi 'dd/MM/yyyy'.
    Xóa bỏ hoàn toàn phần Giờ (HH:mm:ss).
    """
    if raw_val is None or raw_val == "":
        return ""

    if hasattr(raw_val, "strftime"):
        return raw_val.strftime("%d/%m/%Y")

    s = str(raw_val).strip()
    if not s:
        return ""

    try:
        if s.replace('.', '', 1).isdigit() and '.' in s:
            num = float(s)
            if 30000 < num < 70000:
                dt = datetime(1899, 12, 30) + timedelta(days=num)
                return dt.strftime("%d/%m/%Y")
        elif s.isdigit() and 30000 < int(s) < 70000:
            dt = datetime(1899, 12, 30) + timedelta(days=int(s))
            return dt.strftime("%d/%m/%Y")
    except Exception:
        pass

    date_part = s.split(" ")[0].split("T")[0].strip()
    date_part = date_part.replace("-", "/").replace(".", "/")
    parts = date_part.split("/")

    if len(parts) == 3:
        p1, p2, p3 = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if len(p1) == 4: # Format yyyy/MM/dd
            return f"{p3.zfill(2)}/{p2.zfill(2)}/{p1}"
        elif len(p3) == 4 or len(p3) == 2: # Format dd/MM/yyyy hoặc dd/MM/yy
            y = f"20{p3}" if len(p3) == 2 else p3
            return f"{p1.zfill(2)}/{p2.zfill(2)}/{y}"
    elif len(parts) == 2: # Format dd/MM
        now_year = datetime.now().year
        return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{now_year}"

    return s

def _normalize_date_str(raw_date: str) -> str:
    """Wrapper cho parse_odo_date."""
    return parse_odo_date(raw_date)

def _match_master_kho(kho_input: str, master_khos: list) -> str:
    """Khớp tên kho viết tắt hoặc tên thô với danh sách Kho chuẩn."""
    if not kho_input:
        return ""
    k_clean = str(kho_input).strip().lower()

    for mk in master_khos:
        if k_clean == mk.lower().strip():
            return mk

    keywords = {
        "nha trang": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa",
        "đà nẵng": "Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng",
        "liên chiểu": "Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng",
        "hòa xuân": "Kho Giao Hàng Nặng - Hòa Xuân - Đà Nẵng",
        "huế": "Kho Giao Hàng Nặng - Hương Thủy - Huế",
        "vinh": "Kho Giao Hàng Nặng - Vinh - Nghệ An",
        "gia lai": "Kho Giao Hàng Nặng - Pleiku - Gia Lai",
        "pleiku": "Kho Giao Hàng Nặng - Pleiku - Gia Lai",
        "quy nhơn": "Kho Giao Hàng Nặng - Quy Nhơn - Bình Định",
        "hoài nhơn": "Kho Giao Hàng Nặng - Hoài Nhơn - Bình Định",
        "buôn ma thuột": "Kho Giao Hàng Nặng - Buôn Ma Thuột - Đắc Lắk",
        "cam ranh": "Kho Giao Hàng Nặng - Cam Ranh - Khánh Hòa",
        "phan thiết": "Kho Giao Hàng Nặng - Phan Thiết - Bình Thuận",
        "hội an": "Kho Giao Hàng Nặng - Hội An - Quảng Nam",
        "tam kỳ": "Kho Giao Hàng Nặng - Tam Kỳ - Quảng Nam",
        "đông hà": "Kho Giao Hàng Nặng - Đông Hà - Quảng Trị",
        "đồng hới": "Kho Giao Hàng Nặng - Đồng Hới - Quảng Bình",
    }

    for kw, target_kho in keywords.items():
        if kw in k_clean:
            for mk in master_khos:
                if target_kho.lower() in mk.lower():
                    return mk
            return target_kho

    for mk in master_khos:
        mk_clean = mk.lower().replace("kho giao hàng nặng -", "").strip()
        parts = [p.strip() for p in mk_clean.split("-")]
        for p in parts:
            if p and p in k_clean:
                return mk
    return ""  # Không thuộc 25 kho master -> Loại bỏ

def get_master_kho_totals() -> dict:
    """
    Lấy danh sách và số 'Xe chuẩn' của ĐÚNG 25 Kho GXT Miền Trung trực tiếp từ bảng 'Số Lượng Xe GXT Theo Kho' (cột 'Tổng xe đang chạy').
    Không hardcode trong source.
    """
    xe_gxt_data, _ = main.read_csv("xe_gxt")
    kho_totals = defaultdict(int)
    for row in xe_gxt_data:
        kho = (row.get("Kho") or row.get("Kho GXT") or row.get("Tên kho") or row.get("ten kho") or "").strip()
        val = row.get("Tổng xe đang chạy") or row.get("Tá»•ng xe Ä‘ang cháº¡y") or row.get("Tổng xe") or "0"
        try:
            count = int(str(val).strip()) if str(val).strip().isdigit() else 0
        except Exception:
            count = 0
        if kho:
            kho_totals[kho] += count
    return dict(kho_totals)

def fetch_google_sheet_odo_data(force_refresh: bool = False) -> dict:
    """
    Đọc dữ liệu báo ODO từ Google Sheet.
    Spreadsheet ID: 1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo.
    Tự động chọn tab 'THÁNG X' (ví dụ 'THÁNG 7').
    Range đọc: 'THÁNG X'!A:H (Đọc toàn bộ các dòng, không giới hạn A1:Z5000).

    Mapping cột chính:
    Col A (index 0) = Dấu thời gian (Submission Timestamp)
    Col F (index 5) = Kho giao (Warehouse Name)
    Col H (index 7) = Biển kiểm soát (License Plate)

    Returns: dict mapping (date_str, kho_name) -> unique_vehicle_count
    """
    global _ODO_CACHE
    now = time.time()
    if not force_refresh and (now - _ODO_CACHE["timestamp"] < CACHE_TTL_SECONDS) and _ODO_CACHE["data"]:
        return _ODO_CACHE["data"]

    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
    if not os.path.exists(sa_path):
        print(f"[ODO MONITOR] Service Account json missing at {sa_path}")
        return _ODO_CACHE.get("data", {})

    try:
        ssl._create_default_https_context = ssl._create_unverified_context
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)

        meta = service.spreadsheets().get(spreadsheetId=ODO_SHEET_ID).execute()
        sheet_titles = [s['properties']['title'] for s in meta.get('sheets', [])]

        now_month = datetime.now().month
        target_tab = None
        for title in sheet_titles:
            t_upper = title.strip().upper()
            if f"THÁNG {now_month}" in t_upper or f"THANG {now_month}" in t_upper:
                target_tab = title
                break

        if not target_tab:
            month_tabs = [t for t in sheet_titles if "THÁNG" in t.upper() or "THANG" in t.upper()]
            target_tab = month_tabs[-1] if month_tabs else sheet_titles[0]

        print(f"\n===== [ODO MONITOR FETCH API V4] =====")
        print(f"Spreadsheet ID: {ODO_SHEET_ID}")
        print(f"Sheet Name (Tab): '{target_tab}'")
        print(f"Reading Range: '{target_tab}'!A:H")
        
        res = service.spreadsheets().values().get(
            spreadsheetId=ODO_SHEET_ID, range=f"'{target_tab}'!A:H"
        ).execute()
        rows = res.get("values", [])

        total_read_rows = len(rows)
        print(f"[BACKEND LOG] số dòng đọc được từ Sheet: {total_read_rows}")

        if not rows or len(rows) < 2:
            print("[ODO MONITOR WARNING] Sheet rỗng hoặc chỉ có 1 dòng tiêu đề.")
            return {}

        master_khos = list(get_master_kho_totals().keys())

        # (date_str, master_kho_name) -> Set of normalized license plates
        unique_plates_map = defaultdict(set)
        import re

        for idx, r in enumerate(rows[1:], start=2):
            if not r or not any(r):
                continue
            col_a = r[0].strip() if len(r) > 0 else ""
            raw_kho = r[5].strip() if len(r) > 5 else ""
            raw_bien = r[7].strip() if len(r) > 7 else ""

            date_norm = parse_odo_date(col_a)
            kho_norm = _match_master_kho(raw_kho, master_khos)
            clean_plate = re.sub(r'[^A-Z0-9]', '', str(raw_bien).upper()) if raw_bien else ""

            if date_norm and kho_norm and clean_plate:
                unique_plates_map[(date_norm, kho_norm)].add(clean_plate)

        counts = {k: len(v) for k, v in unique_plates_map.items()}

        _ODO_CACHE["timestamp"] = now
        _ODO_CACHE["data"] = counts

        # Print detailed backend logs for today's date
        vn_today_str = get_vn_datetime().strftime("%d/%m/%Y")
        today_khos = {k[1]: len(v) for k, v in unique_plates_map.items() if k[0] == vn_today_str}
        
        print(f"[BACKEND LOG] Ngày hôm nay: {vn_today_str}")
        print(f"[BACKEND LOG] Số kho tìm thấy ODO ngày {vn_today_str}: {len(today_khos)}")
        print(f"[BACKEND LOG] Unique license plates per kho:")
        for k_name, p_cnt in sorted(today_khos.items()):
            print(f"  - {k_name}: {p_cnt} xe")
        print(f"======================================\n")

        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            serializable = {f"{k[0]}|||{k[1]}": v for k, v in counts.items()}
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now, "counts": serializable}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return counts

    except Exception as e:
        print(f"[ODO MONITOR ERROR] Failed to fetch ODO sheet: {e}")
        return _ODO_CACHE.get("data", {})

def get_xe_daily_breakdown(date_str: str) -> tuple:
    """
    Đọc dữ liệu Xe Vận Hành Daily của ngày date_str.
    Returns: (xe_off_dict, xe_tc_dict) mapping kho_name -> count
    """
    records = main._load_xe_daily_records()
    date_norm = parse_odo_date(date_str)

    xe_off = defaultdict(int)
    xe_tc = defaultdict(int)

    for r in records:
        r_date = parse_odo_date(r.get("ngay", ""))
        if r_date == date_norm:
            kho = r.get("ten_kho", "").strip()
            loai = r.get("loai", "").strip()
            sl = int(r.get("so_luong_xe", 1))
            if "không hoạt động" in loai.lower() or "off" in loai.lower() or "hư hỏng" in loai.lower() or "bảo dưỡng" in loai.lower():
                xe_off[kho] += sl
            elif "tăng cường" in loai.lower():
                xe_tc[kho] += sl

    return dict(xe_off), dict(xe_tc)

def calculate_odo_status(target_date: str = None, force_refresh: bool = False) -> dict:
    """
    Tính toán trạng thái ODO cho 25 kho chuẩn GXT Miền Trung theo target_date.
    Công thức: expectedOdo = tongXe + xeTangCuong - xeOff
    """
    if not target_date:
        target_date = datetime.now().strftime("%d/%m/%Y")
    else:
        target_date = parse_odo_date(target_date)

    master_totals = get_master_kho_totals()
    actual_odo_map = fetch_google_sheet_odo_data(force_refresh=force_refresh)
    xe_off_map, xe_tc_map = get_xe_daily_breakdown(target_date)

    details = []
    total_du = 0
    total_thieu = 0
    total_xe_thieu = 0
    total_xe_thua = 0

    for kho, tong_xe in master_totals.items():
        off_cnt = xe_off_map.get(kho, 0)
        tc_cnt = xe_tc_map.get(kho, 0)
        expected_odo = max(0, tong_xe + tc_cnt - off_cnt)

        actual_odo = actual_odo_map.get((target_date, kho), 0)

        if actual_odo == 0:
            for (d, k), cnt in actual_odo_map.items():
                if d == target_date and (kho.lower() in k.lower() or k.lower() in kho.lower()):
                    actual_odo = cnt
                    break

        if actual_odo < expected_odo:
            status = "THIEU"
            diff = expected_odo - actual_odo
            total_thieu += 1
            total_xe_thieu += diff
        elif actual_odo > expected_odo:
            status = "THUA"
            diff = actual_odo - expected_odo
            total_xe_thua += diff
        else:
            status = "DU"
            diff = 0
            total_du += 1

        details.append({
            "ngay": target_date,
            "kho": kho,
            "tong_xe": tong_xe,
            "xe_off": off_cnt,
            "xe_tc": tc_cnt,
            "expected_odo": expected_odo,
            "actual_odo": actual_odo,
            "status": status,
            "diff": diff
        })

    before_golive = is_before_golive(target_date)
    last_updated_str = "Chưa có (Chờ GO-LIVE 18:00 23/07/2026)" if before_golive else datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    summary = {
        "target_date": target_date,
        "total_khos": len(master_totals),
        "du_khos": total_du,
        "thieu_khos": total_thieu,
        "total_xe_thieu": total_xe_thieu,
        "total_xe_thua": total_xe_thua,
        "last_updated": last_updated_str,
        "is_before_golive": before_golive
    }

    return {
        "summary": summary,
        "details": details
    }
