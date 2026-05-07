from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import csv
import os
import io
import time
import urllib.request

app = FastAPI(title="GHN Miền Trung Operations API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Frontend files (index.html, app.js, styles.css) are deployed at root alongside main.py
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend") if os.path.isdir(os.path.join(BASE_DIR, "frontend")) else BASE_DIR
MOCK_DATA_DIR = os.path.join(BASE_DIR, "mock_data")

print(f"[STARTUP] BASE_DIR = {BASE_DIR}")
print(f"[STARTUP] FRONTEND_DIR = {FRONTEND_DIR}")
print(f"[STARTUP] frontend exists = {os.path.exists(FRONTEND_DIR)}")
try:
    print(f"[STARTUP] Files count in BASE_DIR: {len(os.listdir(BASE_DIR))}")
except Exception as e:
    print(f"[STARTUP] Could not list BASE_DIR: {e}")

# ---- GOOGLE SHEETS MAPPING ----
SHEET_ID = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"
GIDS = {
    "gtc":       "0",
    "ontime":    "25240142",
    "returns":   "1169438164",
    "nhan_su":   "660071435",
    "b2b":       "294914730",
    "backlog":   "484018945",
    "nang_suat": "450389975",
    "warnings":  "1291851253",
    "returns_by_client": "1277610973",
    "xe_gxt": "541379955",
    "xe_su_co": "938546985",
    "kho_gxt": "1962460963",
}

CACHE = {}
CACHE_TTL = 300  # 5 minutes

def read_csv(key: str, force: bool = False):
    gid = GIDS.get(key)
    if not gid: return [], 0
    
    now = time.time()
    # Check cache unless force is requested
    if not force and key in CACHE and (now - CACHE[key]['time']) < CACHE_TTL:
        return CACHE[key]['data'], CACHE[key]['time']
        
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    data = []
    try:
        # Added timeout of 10 seconds to prevent hanging
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                if any(row.values()): # skip empty rows
                    data.append(dict(row))
        CACHE[key] = {'time': now, 'data': data}
        print(f"[CACHE] Fetched and cached {key} from Google Sheets. (Force: {force})")
        return data, now
    except Exception as e:
        print(f"[ERROR] Fetching {key} from Google Sheets failed: {e}")
        # Fallback to cache if available, even if expired
        if key in CACHE:
            return CACHE[key]['data'], CACHE[key]['time']
        return [], 0

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
def get_gtc(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("gtc", force)
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- DATA GTC LATEST DATE ----
@app.get("/api/kpi/gtc/latest")
def get_gtc_latest(force: bool = False):
    data, last_sync = read_csv("gtc", force)
    if not data:
        return {"data": [], "last_sync": last_sync}
    dates = sorted(set(r.get("Ngày", "").split(" - ")[0] for r in data if r.get("Ngày")), reverse=True)
    latest = dates[0] if dates else ""
    filtered = [r for r in data if r.get("Ngày", "").startswith(latest)]
    return {"data": filtered, "last_sync": last_sync}

# ---- DATA ONTIME ----
@app.get("/api/kpi/ontime")
def get_ontime(force: bool = False):
    data, last_sync = read_csv("ontime", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA TRẢ HÀNG ----
@app.get("/api/returns")
def get_returns(force: bool = False):
    data, last_sync = read_csv("returns", force)
    return {"data": data, "last_sync": last_sync}

@app.get("/api/returns/by-client")
def get_returns_by_client(force: bool = False):
    data, last_sync = read_csv("returns_by_client", force)
    return {"data": data, "last_sync": last_sync}

@app.get("/api/returns/by-client/columns")
def get_returns_by_client_columns():
    data, _ = read_csv("returns_by_client")
    if not data: return {"error": "No data"}
    return {"columns": list(data[0].keys()), "sample": data[0]}

# ---- NHÂN SỰ ----
@app.get("/api/personnel")
def get_personnel(force: bool = False):
    data, last_sync = read_csv("nhan_su", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA GIAO B2B ----
@app.get("/api/backlog/b2b")
def get_b2b(force: bool = False):
    data, last_sync = read_csv("b2b", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA BACKLOG > 7N ----
@app.get("/api/backlog/critical")
def get_backlog(force: bool = False):
    data, last_sync = read_csv("backlog", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA NĂNG SUẤT NV ----
@app.get("/api/nang-suat")
def get_nang_suat(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("nang_suat", force)
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- AVAILABLE DATES (for GTC filter) ----
@app.get("/api/kpi/gtc/dates")
def get_gtc_dates(force: bool = False):
    data, last_sync = read_csv("gtc", force)
    dates = sorted(set(r.get("Ngày", "") for r in data if r.get("Ngày")), reverse=True)
    return {"data": dates, "last_sync": last_sync}
    
# ---- DATA XE GXT ----
@app.get("/api/xe-gxt")
def get_xe_gxt(force: bool = False):
    data, last_sync = read_csv("xe_gxt", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA XE SỰ CỐ ----
@app.get("/api/xe-su-co")
def get_xe_su_co(force: bool = False):
    data, last_sync = read_csv("xe_su_co", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA KHO GXT ----
@app.get("/api/kho-gxt")
def get_kho_gxt(force: bool = False):
    data, last_sync = read_csv("kho_gxt", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA CẢNH BÁO ----
@app.get("/api/warnings")
def get_warnings(force: bool = False):
    data, last_sync = read_csv("warnings", force)
    return {"data": data, "last_sync": last_sync}

# ---- DEBUG: xem tên cột thực tế ----
@app.get("/api/warnings/columns")
def get_warning_columns():
    data = read_csv("warnings")
    if not data:
        return {"error": "No data", "file": "warnings"}
    return {"columns": list(data[0].keys()), "sample_row": data[0]}

# ---- DASHBOARD OVERVIEW ----
@app.get("/api/dashboard/overview")
def get_overview(force: bool = False):
    gtc_data, gtc_sync     = read_csv("gtc", force)
    b2b_data, _            = read_csv("b2b", force)
    backlog_data, _        = read_csv("backlog", force)
    ontime_data, _         = read_csv("ontime", force)
    returns_data, _        = read_csv("returns", force)
    ns_data, _             = read_csv("nang_suat", force)
    warning_data, warn_sync = read_csv("warnings", force)
    xe_data, _             = read_csv("xe_gxt", force)
    su_co_data, _          = read_csv("xe_su_co", force)
    kho_data, _            = read_csv("kho_gxt", force)
    pers_data, _           = read_csv("personnel", force)

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
    ns_dates = sorted(set(r.get("Ngày", "") for r in ns_data if r.get("Ngày")), reverse=True)
    ns_latest = ns_dates[0] if ns_dates else ""
    ns_latest_rows = [r for r in ns_data if r.get("Ngày") == ns_latest]
    ns_vals = []
    for r in ns_latest_rows:
        try:
            ns_vals.append(float(r.get("avg_delivery_volume_per_hour", 0) or 0))
        except (ValueError, TypeError):
            pass
    avg_nang_suat = round(sum(ns_vals) / len(ns_vals), 1) if ns_vals else 0

    # Warning count (Critical)
    critical_count = len([r for r in warning_data if r.get("Tình hình hiện tại", "") == "Nghiêm trọng"])

    # Backlog LM and KTC totals from warnings sheet
    total_bl_lm = 0
    total_bl_ktc = 0
    for r in warning_data:
        try:
            # Try different column names for backlog
            lm = r.get("backlog lastmile") or r.get("backlog last mile") or r.get("Backlog Last Mile") or 0
            ktc = r.get("backlog ktc") or r.get("Backlog KTC") or 0
            total_bl_lm += int(lm or 0)
            total_bl_ktc += int(ktc or 0)
        except (ValueError, TypeError):
            pass

    # Total Xe GXT
    total_xe = sum(int(r.get("Tổng xe đang chạy", 0) or 0) for r in xe_data)

    # Total Kho GXT
    total_kho_gxt = len(kho_data)
    
    # Total Personnel (Delivery Staff)
    total_delivery_staff = len([r for r in pers_data if r.get('position_name') == 'Delivery Staff'])

    return {
        "avg_gtc": avg_gtc,
        "latest_date": latest_date,
        "avg_ontime": avg_ontime,
        "total_backlog_7n": total_backlog,
        "total_b2b_priority": b2b_priority,
        "avg_fd_return": avg_fd,
        "avg_nang_suat": avg_nang_suat,
        "critical_warnings": critical_count,
        "total_backlog_lm": total_bl_lm,
        "total_backlog_ktc": total_bl_ktc,
        "total_backlog_all": total_bl_lm + total_bl_ktc,
        "total_xe_gxt": total_xe,
        "total_kho_gxt": total_kho_gxt,
        "total_personnel": total_delivery_staff,
        "last_sync": max(gtc_sync, warn_sync)
    }

# ---- GTC BY KHO (latest date) ----
@app.get("/api/kpi/gtc/by-kho")
def get_gtc_by_kho(force: bool = False):
    data, last_sync = read_csv("gtc", force)
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
    return {"data": sorted(result, key=lambda x: x["pct_gtc"]), "last_sync": last_sync}

# ---- TELEGRAM REPORTING ----
import httpx
from datetime import datetime

# Cấu hình Telegram
TELEGRAM_TOKEN = "8161133962:AAHsGqX7D5z0IGJDTvJTSrMIeu1NyiQHv-E"
CHAT_ID = "-1002712779761"
ADMIN_KEY = "gxt1103" # Mã bí mật để gửi báo cáo

@app.post("/api/telegram/report")
async def send_telegram_report(payload: dict):
    try:
        # Kiểm tra mã bí mật
        client_key = payload.get("key", "")
        if client_key != ADMIN_KEY:
            return {"status": "error", "message": "Bạn không có quyền thực hiện hành động này."}

        message = payload.get("message", "")
        if not message:
            return {"status": "error", "message": "Nội dung báo cáo trống."}

        # Gửi qua Telegram API
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            })
            
        if resp.status_code == 200:
            return {"status": "success", "message": "Báo cáo đã được gửi!"}
        else:
            return {"status": "error", "message": f"Telegram Error: {resp.text}"}

    except Exception as e:
        print(f"[TELEGRAM] Error: {str(e)}")
        return {"status": "error", "message": str(e)}

# ---- SERVE FRONTEND ----
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    print(f"[STARTUP] StaticFiles mounted from {FRONTEND_DIR}")
else:
    print(f"[STARTUP] WARNING: frontend/ directory not found at {FRONTEND_DIR}")

@app.get("/app.js")
def read_js():
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    return FileResponse(os.path.join(BASE_DIR, "app.js"), media_type="application/javascript")

@app.get("/styles.css")
def read_css():
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    return FileResponse(os.path.join(BASE_DIR, "styles.css"), media_type="text/css")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    index_path_base = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path_base):
        return FileResponse(index_path_base)
    return {
        "message": "Frontend not found",
        "base_dir": BASE_DIR,
        "frontend_dir": FRONTEND_DIR,
        "frontend_exists": os.path.exists(FRONTEND_DIR),
        "files_in_base": os.listdir(BASE_DIR)
    }
