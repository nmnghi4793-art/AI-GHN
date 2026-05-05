from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import csv
import os

app = FastAPI(title="GHN Miền Trung Operations API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_DATA_DIR = BASE_DIR
FRONTEND_DIR = BASE_DIR

# ---- FILE NAME MAPPING (REAL FILES) ----
FILES = {
    "gtc":       "Miền Trung - Data GTC.csv",
    "ontime":    "Miền Trung - Data Ontime Gán.csv",
    "returns":   "Miền Trung - Data Trả Hàng.csv",
    "nhan_su":   "Miền Trung - Nhân Sự.csv",
    "b2b":       "Miền Trung - Data giao B2B.csv",
    "backlog":   "Miền Trung - Data Backlog _ 7n.csv",
    "nang_suat": "Miền Trung - Data Năng Suất NV.csv",
    "warnings":  "Miền Trung - Cảnh Báo.csv",
}

def read_csv(key: str):
    filename = FILES.get(key, key)
    filepath = os.path.join(MOCK_DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
    data = []
    with open(filepath, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(dict(row))
    return data

def parse_pct_vn(s: str) -> float:
    """Parse Vietnamese-format percentage like '90,03%' -> 90.03"""
    if not s:
        return 0.0
    s = s.strip().replace('%', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

# ---- DATA GTC ----
@app.get("/api/kpi/gtc")
def get_gtc(date: str = Query(None)):
    data = read_csv("gtc")
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return data

# ---- DATA GTC LATEST DATE ----
@app.get("/api/kpi/gtc/latest")
def get_gtc_latest():
    data = read_csv("gtc")
    if not data:
        return []
    dates = sorted(set(r.get("Ngày", "").split(" - ")[0] for r in data if r.get("Ngày")), reverse=True)
    latest = dates[0] if dates else ""
    return [r for r in data if r.get("Ngày", "").startswith(latest)]

# ---- DATA ONTIME ----
@app.get("/api/kpi/ontime")
def get_ontime():
    return read_csv("ontime")

# ---- DATA TRẢ HÀNG ----
@app.get("/api/returns")
def get_returns():
    return read_csv("returns")

# ---- NHÂN SỰ ----
@app.get("/api/personnel")
def get_personnel():
    return read_csv("nhan_su")

# ---- DATA GIAO B2B ----
@app.get("/api/backlog/b2b")
def get_b2b():
    return read_csv("b2b")

# ---- DATA BACKLOG > 7N ----
@app.get("/api/backlog/critical")
def get_backlog():
    return read_csv("backlog")

# ---- DATA NĂNG SUẤT NV ----
@app.get("/api/nang-suat")
def get_nang_suat(date: str = Query(None)):
    data = read_csv("nang_suat")
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return data

# ---- AVAILABLE DATES (for GTC filter) ----
@app.get("/api/kpi/gtc/dates")
def get_gtc_dates():
    data = read_csv("gtc")
    dates = sorted(set(r.get("Ngày", "") for r in data if r.get("Ngày")), reverse=True)
    return dates
    
# ---- DATA CẢNH BÁO ----
@app.get("/api/warnings")
def get_warnings():
    return read_csv("warnings")

# ---- DASHBOARD OVERVIEW ----
@app.get("/api/dashboard/overview")
def get_overview():
    gtc_data    = read_csv("gtc")
    b2b_data    = read_csv("b2b")
    backlog_data = read_csv("backlog")
    ontime_data = read_csv("ontime")
    returns_data = read_csv("returns")

    # Latest GTC date
    dates = sorted(set(r.get("Ngày", "") for r in gtc_data if r.get("Ngày")), reverse=True)
    latest_date = dates[0] if dates else ""
    latest_rows = [r for r in gtc_data if r.get("Ngày") == latest_date]

    total_don_gan = sum(int(r.get("Số đơn gán", 0) or 0) for r in latest_rows)
    total_don_gtc = sum(int(r.get("Số đơn GTC", 0) or 0) for r in latest_rows)
    avg_gtc = round((total_don_gtc / total_don_gan * 100), 2) if total_don_gan else 0

    # Avg Ontime latest day
    on_dates = sorted(set(r.get("Ngày", "") for r in ontime_data if r.get("Ngày")), reverse=True)
    on_latest = on_dates[0] if on_dates else ""
    on_latest_rows = [r for r in ontime_data if r.get("Ngày") == on_latest]
    ontime_vals = []
    for r in on_latest_rows:
        val = parse_pct_vn(r.get("%GTC/ nhận mới", ""))
        if val > 0:
            ontime_vals.append(val)
    avg_ontime = round(sum(ontime_vals) / len(ontime_vals), 2) if ontime_vals else 0

    # Backlog count
    total_backlog = len(backlog_data)

    # B2B priority count (only "trong hôm nay" & "trong ngày mai")
    b2b_priority = len([r for r in b2b_data if
        r.get("Mức độ ưu tiên", "").startswith("1:") or
        r.get("Mức độ ưu tiên", "").startswith("2:")])

    # FD average
    fd_vals = []
    for r in returns_data:
        val = parse_pct_vn(r.get("% FD", ""))
        if val >= 0:
            fd_vals.append(val)
    avg_fd = round(sum(fd_vals) / len(fd_vals), 2) if fd_vals else 0

    # Năng Suất average (latest day)
    ns_dates = sorted(set(r.get("Ngày", "") for r in read_csv("nang_suat") if r.get("Ngày")), reverse=True)
    ns_latest = ns_dates[0] if ns_dates else ""
    ns_latest_rows = [r for r in read_csv("nang_suat") if r.get("Ngày") == ns_latest]
    ns_vals = []
    for r in ns_latest_rows:
        try:
            ns_vals.append(float(r.get("avg_delivery_volume_per_hour", 0) or 0))
        except ValueError:
            pass
    avg_nang_suat = round(sum(ns_vals) / len(ns_vals), 1) if ns_vals else 0

    # Warning count (Critical)
    warning_data = read_csv("warnings")
    critical_count = len([r for r in warning_data if r.get("Tình hình hiện tại", "") == "Nghiêm trọng"])

    return {
        "avg_gtc": avg_gtc,
        "latest_date": latest_date,
        "avg_ontime": avg_ontime,
        "total_backlog_7n": total_backlog,
        "total_b2b_priority": b2b_priority,
        "avg_fd_return": avg_fd,
        "avg_nang_suat": avg_nang_suat,
        "critical_warnings": critical_count,
    }

# ---- GTC BY KHO (latest date) ----
@app.get("/api/kpi/gtc/by-kho")
def get_gtc_by_kho():
    data = read_csv("gtc")
    dates = sorted(set(r.get("Ngày", "").split(" - ")[0] for r in data if r.get("Ngày")), reverse=True)
    latest = dates[0] if dates else ""
    rows = [r for r in data if r.get("Ngày", "").startswith(latest)]
    result = []
    for r in rows:
        pct = parse_pct_vn(r.get("% GTC", "0"))
        result.append({
            "kho": r.get("Kho", ""),
            "so_don_gan": int(r.get("Số đơn gán", 0) or 0),
            "so_don_gtc": int(r.get("Số đơn GTC", 0) or 0),
            "pct_gtc": pct,
        })
    return sorted(result, key=lambda x: x["pct_gtc"])

# ---- SERVE FRONTEND ----
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found"}
