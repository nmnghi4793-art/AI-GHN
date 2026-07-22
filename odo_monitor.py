import os
import sys
import time
import ssl
import json
import secrets
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import main

ODO_SHEET_ID = os.environ.get("ODO_SHEET_ID", "1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo")
CACHE_FILE = os.path.join(BASE_DIR, "scratch", "odo_cache.json")
LOGS_FILE = os.path.join(BASE_DIR, "scratch", "odo_monitor_logs.json")

_ODO_CACHE = {
    "timestamp": 0,
    "data": {}
}

CACHE_TTL_SECONDS = 180  # 3 minutes cache TTL

def parse_odo_date(raw_val) -> str:
    """
    Hỗ trợ đọc và chuyển đổi mọi định dạng ngày từ Google Sheets về chuỗi 'dd/MM/yyyy'.
    Xóa bỏ hoàn toàn phần Giờ (HH:mm:ss).
    Hỗ trợ:
      - Chuỗi 'dd/MM/yyyy HH:mm:ss' (vd: 22/07/2026 17:33:19)
      - Chuỗi 'yyyy-MM-dd HH:mm:ss' (vd: 2026-07-22 17:33:19)
      - Chuỗi 'dd/MM/yyyy' hoặc 'yyyy/MM/dd'
      - Serial date Google Sheets (ví dụ float/int 46225.73)
      - Objects datetime / date
    """
    if raw_val is None or raw_val == "":
        return ""

    if hasattr(raw_val, "strftime"):
        return raw_val.strftime("%d/%m/%Y")

    s = str(raw_val).strip()
    if not s:
        return ""

    # Nếu là Serial Date của Google Sheets (vd: 46225 hoặc 46225.73)
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

    # Tách phần ngày và phần giờ (nếu có ' ' hoặc 'T')
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

    # Check exact match
    for mk in master_khos:
        if k_clean == mk.lower().strip():
            return mk

    # Check substring / alias matching
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

    # Fallback fuzzy substring match
    for mk in master_khos:
        mk_clean = mk.lower().replace("kho giao hàng nặng -", "").strip()
        parts = [p.strip() for p in mk_clean.split("-")]
        for p in parts:
            if p and p in k_clean:
                return mk
    return kho_input

def get_master_kho_totals() -> dict:
    """Lấy số xe chuẩn (tongXe) của từng kho từ module KPI Xe GXT hiện có."""
    xe_gxt_data, _ = main.read_csv("xe_gxt")
    kho_totals = defaultdict(int)
    for row in xe_gxt_data:
        kho = main._flex_get(row, ["tên kho", "ten kho", "kho"])
        sl = main._flex_get(row, ["số lượng xe", "so luong xe", "sl xe", "sl_xe", "số xe"], "1")
        try:
            sl_num = int(sl)
        except Exception:
            sl_num = 1
        if kho:
            kho_totals[kho] += sl_num
    return dict(kho_totals)

def fetch_google_sheet_odo_data(force_refresh: bool = False) -> dict:
    """
    Đọc dữ liệu báo ODO từ Google Sheet (ID: 1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo).
    Tự động nhận biết tab tháng hiện tại (ví dụ: 'THÁNG 7').
    Bỏ hoàn toàn giờ HH:mm:ss khi group và đếm ODO.
    Returns: dict mapping (date_str, kho_name) -> count
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

        # 1. Tìm tên tab tháng hiện tại
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

        print(f"[ODO MONITOR] Fetching ODO data from tab '{target_tab}'...")
        res = service.spreadsheets().values().get(
            spreadsheetId=ODO_SHEET_ID, range=f"{target_tab}!A1:Z5000"
        ).execute()
        rows = res.get("values", [])

        if not rows or len(rows) < 2:
            print("[ODO MONITOR WARNING] Google Sheet returned empty rows or header only.")
            return {}

        master_khos = list(get_master_kho_totals().keys())

        # Logging Yêu cầu 6: In giá trị raw 5 ô đầu cột A và sau khi parse
        print("--- [ODO MONITOR LOG] TOP 5 RAW COLUMN A & PARSED DATES ---")
        for i, r in enumerate(rows[1:6], 1):
            raw_a = r[0] if len(r) > 0 else ""
            parsed_a = parse_odo_date(raw_a)
            raw_kho = r[5] if len(r) > 5 else ""
            print(f"  Row {i}: Raw Col A = {repr(raw_a)} -> Parsed = {repr(parsed_a)} | Kho = {repr(raw_kho)}")

        counts = defaultdict(int)
        for r in rows[1:]:
            if not r or len(r) < 6:
                continue
            col_a = r[0].strip() if len(r) > 0 else ""
            col_g = r[6].strip() if len(r) > 6 else ""
            raw_kho = r[5].strip() if len(r) > 5 else ""

            raw_date = col_g if col_g else col_a
            date_norm = parse_odo_date(raw_date)
            kho_norm = _match_master_kho(raw_kho, master_khos)

            if date_norm and kho_norm:
                counts[(date_norm, kho_norm)] += 1

        res_dict = dict(counts)
        _ODO_CACHE["timestamp"] = now
        _ODO_CACHE["data"] = res_dict

        # Save cache file
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            serializable = {f"{k[0]}|||{k[1]}": v for k, v in res_dict.items()}
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now, "counts": serializable}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        print(f"[ODO MONITOR] Successfully parsed & cached {len(rows)-1} rows into {len(res_dict)} (date, kho) counts.")
        return res_dict

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
    Tính toán trạng thái ODO của tất cả các kho theo target_date.
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

        # Fuzzy fallback lookup if exact key not matched
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

    summary = {
        "target_date": target_date,
        "total_khos": len(master_totals),
        "du_khos": total_du,
        "thieu_khos": total_thieu,
        "total_xe_thieu": total_xe_thieu,
        "total_xe_thua": total_xe_thua,
        "last_updated": datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    }

    return {
        "summary": summary,
        "details": details
    }
