import sys
import os
import io
import secrets
import time
import json
import asyncio
from collections import defaultdict
import threading

# Fix Playwright NotImplementedError on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup encoding for windows stdout / log output (Windows-only to avoid issues)
if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def load_env():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
        current_dir = os.path.dirname(current_dir)

load_env()

from fastapi import FastAPI, Query, Header, HTTPException, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
import csv
import io
import urllib.request

app = FastAPI(
    title="GHN Miền Trung Operations API",
    docs_url=None,      # Tắt Swagger UI công khai
    redoc_url=None,     # Tắt ReDoc công khai
    openapi_url=None,   # Tắt OpenAPI schema công khai
)

# ---- CORS: Chỉ cho phép origin cụ thể, không dùng wildcard ----
_ALLOWED_ORIGINS = [
    "https://ai-ghn-gxt.up.railway.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,   # False khi không dùng cookie cross-origin
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"],
)

# ---- SECURITY HEADERS MIDDLEWARE ----
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Thêm security headers vào tất cả HTTP response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"]          = "DENY"
        response.headers["X-Content-Type-Options"]   = "nosniff"
        response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"]= "max-age=31536000; includeSubDomains; preload"
        response.headers["Permissions-Policy"]       = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"]  = (
            "default-src 'self'; "
            # unsafe-inline cần thiết do onclick attrs trong index.html;
            # refactor to addEventListener để xóa dc unsafe-inline sau này
            "script-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com 'unsafe-inline'; "
            "style-src 'self' fonts.googleapis.com cdnjs.cloudflare.com cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' fonts.gstatic.com cdnjs.cloudflare.com data:; "
            "img-src 'self' data: *.tile.openstreetmap.org; "
            "connect-src 'self' api.telegram.org; "
            "frame-ancestors 'none'; "           # chống Clickjacking (tăng cường X-Frame-Options)
            "base-uri 'self'; "                  # chống Base Tag Injection
            "object-src 'none'; "                # chặn Flash / plugins
            "form-action 'self';"
        )
        return response

class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Đo thời gian phản hồi của tất cả API routes."""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        path = request.url.path
        if path.startswith("/api/"):
            print(f"[PERFORMANCE LOG] API {request.method} {path} responded in {duration:.3f}s.")
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PerformanceLoggingMiddleware)

# ---- RATE LIMITING (in-memory, không cần thêm dependency) ----
_LOGIN_ATTEMPTS: dict = defaultdict(list)
_RATE_LIMIT_MAX = 5       # Tối đa 5 lần thử
_RATE_LIMIT_WINDOW = 60   # Trong vòng 60 giây

def _check_login_rate_limit(ip: str) -> bool:
    """Trả về True nếu được phép, False nếu bị rate limit."""
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    # Xóa các attempt cũ ngoài cửa sổ thời gian
    _LOGIN_ATTEMPTS[ip] = [t for t in _LOGIN_ATTEMPTS[ip] if t > cutoff]
    if len(_LOGIN_ATTEMPTS[ip]) >= _RATE_LIMIT_MAX:
        return False
    _LOGIN_ATTEMPTS[ip].append(now)
    return True

# ---- API AUTH: Bearer token / session validation ----
_API_TOKEN = os.environ.get("API_SECRET_TOKEN", "")

# NOTE: require_api_token is defined below after _ACTIVE_SESSIONS is initialized.
# This placeholder is intentionally left blank — do NOT add a function here.


# ---- ADMIN KEY: dùng cho các endpoint nhạy cảm ----
_ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

def require_admin_key(x_admin_key: str = Header(None)):
    """Dependency: bảo vệ endpoint admin bằng X-Admin-Key header."""
    if not _ADMIN_KEY:
        raise HTTPException(status_code=503, detail="Admin key not configured")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, _ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Forbidden: Invalid admin key")

@app.on_event("startup")
async def startup_event():
    import asyncio
    # --- Telegram Bot ---
    try:
        from telegram_bot import run_bot
        asyncio.create_task(run_bot())
        print("[STARTUP] Đã kích hoạt background task cho Telegram Bot.")
    except Exception as e:
        print(f"[STARTUP ERROR] Không thể đăng ký background task cho Telegram Bot: {e}")

    # --- Giao Hang Scheduler ---
    try:
        from giao_hang_scheduler import run_giao_hang_scheduler
        asyncio.create_task(run_giao_hang_scheduler())
        print("[STARTUP] Đã kích hoạt Giao Hàng Scheduler (09:30 & 13:30).")
    except Exception as e:
        print(f"[STARTUP ERROR] Không thể đăng ký Giao Hàng Scheduler: {e}")

    # --- Collect Money Scheduler ---
    try:
        from collect_money_scheduler import run_collect_money_scheduler
        asyncio.create_task(run_collect_money_scheduler())
        print("[STARTUP] Đã kích hoạt Thu Tiền - Bắn Kiểm Scheduler (21:00, 22:00 & 23:00).")
    except Exception as e:
        print(f"[STARTUP ERROR] Không thể đăng ký Thu Tiền - Bắn Kiểm Scheduler: {e}")

    # --- Van Hanh Scheduler ---
    try:
        from vanhanh_scheduler import run_vanhanh_scheduler
        asyncio.create_task(run_vanhanh_scheduler())
        print("[STARTUP] Đã kích hoạt Báo Cáo Tồn Phiếu Vận Hành GXT (Mỗi 5 phút).")
    except Exception as e:
        print(f"[STARTUP ERROR] Không thể đăng ký Van Hanh Scheduler: {e}")

    # --- Dashboard Sync Scheduler ---
    try:
        asyncio.create_task(run_dashboard_sync_scheduler())
        print("[STARTUP] Đã kích hoạt Dashboard Sync Scheduler (Đồng bộ nền & cache).")
    except Exception as e:
        print(f"[STARTUP ERROR] Không thể đăng ký Dashboard Sync Scheduler: {e}")


# ---- ADMIN: Test Giao Hang Report ----
@app.get("/api/giao-hang/test", dependencies=[Depends(require_admin_key)])
async def test_giao_hang(mode: str = "09:30"):
    """
    Trigger bao cao giao hang ngay lap tuc (khong can doi 09:30/13:30).
    mode: "09:30" hoac "13:30"
    Bao ve bang X-Admin-Key header.
    """
    if mode not in ("09:30", "13:30"):
        return {"status": "error", "message": "mode phai la '09:30' hoac '13:30'"}
    try:
        from giao_hang_scheduler import run_giao_hang_report, _sent_today
        # Reset trang thai de cho phep gui lai (tranh bi chặn bởi _sent_today)
        _sent_today.pop(mode, None)
        import asyncio
        asyncio.create_task(run_giao_hang_report(mode))
        return {
            "status": "ok",
            "message": f"Da kich hoat bao cao [{mode}]. Kiem tra Telegram sau vai giay.",
            "mode": mode,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---- ADMIN: Test Collect Money Report ----
@app.get("/api/collect-money/test", dependencies=[Depends(require_admin_key)])
async def test_collect_money():
    """
    Trigger bao cao thu tien - ban kiem ngay lap tuc.
    Bao ve bang X-Admin-Key header.
    """
    try:
        from collect_money_scheduler import run_collect_money_report, _sent_today
        # Reset trang thai de cho phep gui lai (tranh bi chặn bởi _sent_today)
        _sent_today.pop("test", None)
        import asyncio
        asyncio.create_task(run_collect_money_report("test"))
        return {
            "status": "ok",
            "message": "Da kich hoat bao cao thu tien - ban kiem. Kiem tra Telegram sau vai giay.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
# Sheet IDs — luôn load từ env var; fallback chỉ dùng khi dev local
_SHEET_ID_FALLBACK     = "1Y6ty2RlGYh7Zpo4V1xOUQChyag1p15FvyxBQNaaPlCk"
_ODO_SHEET_ID_FALLBACK = "1frGuwcXD3oTcvY8wt62CqA3j0i6Ub2YrksF_tUIFrcY"
SHEET_ID     = os.environ.get("SHEET_ID")     or _SHEET_ID_FALLBACK
ODO_SHEET_ID = os.environ.get("ODO_SHEET_ID") or _ODO_SHEET_ID_FALLBACK
if not os.environ.get("SHEET_ID"):
    print("[SECURITY WARNING] SHEET_ID not in env vars — using hardcoded fallback. "
          "Set SHEET_ID in Railway environment for production.")
GIDS = {
    "gtc":       "0",
    "returns":   "1169438164",
    "nhan_su":   "660071435",
    "personnel": "660071435",
    "b2b":       "294914730",
    "backlog":   "484018945",
    "nang_suat": "450389975",
    "warnings":  "1291851253",
    "returns_by_client": "1277610973",
    "xe_su_co":  "938546985",
    "kho_gxt":   "1962460963",
    "xe_gxt":    "541379955",
    "don_tao":   "869576788",
    "odo_sheet": "0",  # Tab đầu tiên của ODO_SHEET_ID
    "gtc_b2b":   "796633647",
    "don_b2b":   "429619028",
}

CACHE = {}
CACHE_TTL = 300  # 5 minutes

CSV_MAPPING = {
    "Tá»‰nh": "Tỉnh", "TÃªn NCC": "Tên NCC", "Loáº¡i xe": "Loại xe",
    "Tá»•ng xe Ä‘ang cháº¡y": "Tổng xe đang chạy", "Ca lÃ m viá»‡c": "Ca làm việc",
    "GÃ­a thuÃª xe": "Giá thuê xe", "Biá»ƒn Sá»‘": "Biển Số",
    "Ná»™i Dung Chi Tiáº¿t": "Nội Dung Chi Tiết", "Biá»ƒn Sá»‘ Xe": "Biển Số Xe",
    "TÃªn Kho GXT": "Tên Kho GXT", "Diá»‡n TÃ­ch": "Diện Tích",
    "Ä á»‹a chá»‰ kho": "Địa chỉ kho", "TÃ¬nh tráº¡ng": "Tình trạng",
    "KL gÃ¡n": "KL gán", "Ä‘Æ¡n táº¡o N-1": "đơn tạo N-1", "Ä‘Æ¡n gtc N-1": "đơn gtc N-1",
    "Loáº¡i": "Loại", "Ngày nháº­p kho": "Ngày nhập kho", "Ä Ã£ lÆ°u kho (ngày)": "Đã lưu kho (ngày)",
    "Ä á»‹a chá»‰ giao": "Địa chỉ giao", "Thá» i gian": "Thời gian",
    "Tá»•ng Ä‘Æ¡n tráº£": "Tổng đơn trả", "Tráº£ hÃ ng tá»•ng": "Trả hàng tổng",
    "Tráº£ hÃ ng SHOPEE Bulky": "Trả hàng SHOPEE Bulky", "Tráº£ hÃ ng TTS Bulky": "Trả hàng TTS Bulky",
    "Tráº£ hÃ ng SME": "Trả hàng SME", "Tráº£ hÃ ng B2B": "Trả hàng B2B",
    "Tráº£ hÃ ng Ecommerce": "Trả hàng Ecommerce", "ThÃ¢m niÃªn": "Thâm niên",
    "TÃªn vá»‹ trÃ­": "Tên vị trí", "Há»  tÃªn": "Họ tên", "Loáº¡i HÄ ": "Loại HĐ",
    "PhÃ²ng ban": "Phòng ban", "Sá»‘ ngày trá»Ÿ vá»  ngày thÆ°á» ng": "Số ngày trở về ngày thường",
    "Sá»‘ Ä‘Æ¡n gÃ¡n": "Số đơn gán", "Sá»‘ Ä‘Æ¡n GTC": "Số đơn GTC",
    "Sá»‘ Ä‘Æ¡n tráº£": "Số đơn trả", "Tá»•ng Ä‘Æ¡n táº¡o": "Tổng đơn tạo",
    "Tá»•ng khá»‘i lÆ°á»£ng (KG)": "Tổng khối lượng (KG)", "so ngay": "so ngay",
    "??n t?o N-1": "đơn tạo N-1", "??n gtc N-1": "đơn gtc N-1", "GÃ­a": "Giá"
}

import json

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "cache_sheets")

def _get_persistent_cache(key: str):
    """Đọc cache từ đĩa nếu memory cache trống."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached and "time" in cached and "data" in cached:
                    return cached["data"], cached["time"]
    except Exception as e:
        print(f"[CACHE PERSISTENT] Error reading {key} from disk: {e}")
    return None, 0

def _save_persistent_cache(key: str, data: list, cache_time: float):
    """Ghi cache xuống đĩa."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"time": cache_time, "data": data}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE PERSISTENT] Error writing {key} to disk: {e}")

def read_csv(key: str, force: bool = False):
    gid = GIDS.get(key)
    if not gid: return [], 0
    
    now = time.time()
    # 1. Check memory cache first
    if not force and key in CACHE and (now - CACHE[key]['time']) < CACHE_TTL:
        return CACHE[key]['data'], CACHE[key]['time']
        
    # 2. Check disk cache if memory cache is empty
    if not force and key not in CACHE:
        disk_data, disk_time = _get_persistent_cache(key)
        if disk_data and (now - disk_time) < CACHE_TTL:
            CACHE[key] = {'time': disk_time, 'data': disk_data}
            return disk_data, disk_time
            
    current_sheet_id = ODO_SHEET_ID if key == "odo_sheet" else SHEET_ID
    url = f"https://docs.google.com/spreadsheets/d/{current_sheet_id}/export?format=csv&gid={gid}"
    data = []
    try:
        # Added timeout of 10 seconds to prevent hanging
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                if any(row.values()): # skip empty rows
                    cleaned_row = {}
                    for k, v in row.items():
                        if k is None: continue
                        cleaned_row[k] = v # Giữ lại key thô nguyên bản
                        new_k = k
                        for bad, good in CSV_MAPPING.items():
                            if bad in new_k: new_k = new_k.replace(bad, good)
                        if new_k != k:
                            cleaned_row[new_k] = v # Bổ sung thêm bản sao với key tiếng Việt chuẩn
                    data.append(cleaned_row)
        CACHE[key] = {'time': now, 'data': data}
        _save_persistent_cache(key, data, now)
        print(f"[CACHE] Fetched and cached {key} from Google Sheets. (Force: {force})")
        return data, now
    except Exception as e:
        print(f"[ERROR] Fetching {key} from Google Sheets failed: {e}")
        # Fallback to cache if available, even if expired
        if key in CACHE:
            return CACHE[key]['data'], CACHE[key]['time']
        # Fallback to disk cache if available
        disk_data, disk_time = _get_persistent_cache(key)
        if disk_data:
            CACHE[key] = {'time': disk_time, 'data': disk_data}
            return disk_data, disk_time
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

# ---- AUTH: Login endpoint (thay thế client-side auth) ----
# Credentials lấy từ environment variables, KHÔNG hardcode
_DASH_USER = os.environ.get("DASH_USER", "giaohangnangmientrung")
_DASH_PASS = os.environ.get("DASH_PASS", "GXT@MienTrung2026!")

if not _DASH_USER or not _DASH_PASS:
    print("[WARNING] DASH_USER hoac DASH_PASS chua duoc cau hinh trong env vars.")

# Session token store (in-memory, đủ cho single-instance Railway)
_ACTIVE_SESSIONS: dict = {}
SESSION_TTL = 8 * 3600  # 8 tiếng

@app.post("/api/auth/login")
async def login(request: Request, payload: dict):
    """Xác thực username/password, trả về session token."""
    # Rate limiting: tối đa 5 lần thử/phút/IP
    client_ip = request.client.host if request.client else "unknown"
    if not _check_login_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều lần thử đăng nhập. Vui lòng đợi 1 phút.",
            headers={"Retry-After": "60"}
        )

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    # Dùng compare_digest để tránh timing attack
    user_ok = secrets.compare_digest(username, _DASH_USER)
    pass_ok  = secrets.compare_digest(password, _DASH_PASS)

    if user_ok and pass_ok:
        token = secrets.token_urlsafe(32)
        _ACTIVE_SESSIONS[token] = time.time()
        # Dọn session cũ
        expired = [k for k, t in _ACTIVE_SESSIONS.items() if time.time() - t > SESSION_TTL]
        for k in expired: del _ACTIVE_SESSIONS[k]
        return {"token": token}
    else:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")

@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    """Hủy session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        _ACTIVE_SESSIONS.pop(token, None)
    return {"status": "ok"}

def require_api_token(authorization: str = Header(None)):
    """Override: kiểm tra session token từ _ACTIVE_SESSIONS (nếu API_SECRET_TOKEN không cấu hình)."""
    if _API_TOKEN:
        # Mode prod: dùng static API token
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = authorization[len("Bearer "):]
        if not secrets.compare_digest(token, _API_TOKEN):
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        # Mode session: kiểm tra session token
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = authorization[len("Bearer "):]
        if token not in _ACTIVE_SESSIONS:
            raise HTTPException(status_code=403, detail="Session expired")
        # Gia hạn session
        _ACTIVE_SESSIONS[token] = time.time()

# ---- DATA GTC ----
@app.get("/api/kpi/gtc", dependencies=[Depends(require_api_token)])
def get_gtc(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("gtc", force)
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- DATA GTC LATEST DATE ----
@app.get("/api/kpi/gtc/latest", dependencies=[Depends(require_api_token)])
def get_gtc_latest(force: bool = False):
    data, last_sync = read_csv("gtc", force)
    if not data:
        return {"data": [], "last_sync": last_sync}
    dates = sorted(set(r.get("Ngày", "").split(" - ")[0] for r in data if r.get("Ngày")), reverse=True)
    latest = dates[0] if dates else ""
    filtered = [r for r in data if r.get("Ngày", "").startswith(latest)]
    return {"data": filtered, "last_sync": last_sync}

# ---- DATA ONTIME ----
@app.get("/api/kpi/ontime", dependencies=[Depends(require_api_token)])
def get_ontime(force: bool = False):
    import time
    return {"data": [], "last_sync": time.time()}

# ---- DATA TRẢ HÀNG ----
@app.get("/api/kpi/gtc-b2b", dependencies=[Depends(require_api_token)])
def get_gtc_b2b(force: bool = False):
    data, last_sync = read_csv("gtc_b2b", force)
    return {"data": data, "last_sync": last_sync}

@app.get("/api/kpi/don-b2b", dependencies=[Depends(require_api_token)])
def get_don_b2b(force: bool = False):
    data, last_sync = read_csv("don_b2b", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA TRẢ HÀNG ----
@app.get("/api/returns", dependencies=[Depends(require_api_token)])
def get_returns(force: bool = False):
    data, last_sync = read_csv("returns", force)
    return {"data": data, "last_sync": last_sync}

@app.get("/api/returns/by-client", dependencies=[Depends(require_api_token)])
def get_returns_by_client(force: bool = False):
    data, last_sync = read_csv("returns_by_client", force)
    return {"data": data, "last_sync": last_sync}

# ---- NHÂN SỰ ----
@app.get("/api/personnel", dependencies=[Depends(require_api_token)])
def get_personnel(force: bool = False):
    data, last_sync = read_csv("nhan_su", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA GIAO B2B ----
@app.get("/api/backlog/b2b", dependencies=[Depends(require_api_token)])
def get_b2b(force: bool = False):
    data, last_sync = read_csv("b2b", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA BACKLOG > 7N ----
@app.get("/api/backlog/critical", dependencies=[Depends(require_api_token)])
def get_backlog(force: bool = False):
    data, last_sync = read_csv("backlog", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA NĂNG SUẤT NV ----
@app.get("/api/nang-suat", dependencies=[Depends(require_api_token)])
def get_nang_suat(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("nang_suat", force)
    if date:
        data = [r for r in data if r.get("Ngày", "").startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- AVAILABLE DATES (for GTC filter) ----
@app.get("/api/kpi/gtc/dates", dependencies=[Depends(require_api_token)])
def get_gtc_dates(force: bool = False):
    data, last_sync = read_csv("gtc", force)
    dates = sorted(set(r.get("Ngày", "") for r in data if r.get("Ngày")), reverse=True)
    return {"data": dates, "last_sync": last_sync}

# ---- DATA XE GXT ----
@app.get("/api/xe-gxt", dependencies=[Depends(require_api_token)])
def get_xe_gxt(force: bool = False):
    data, last_sync = read_csv("xe_gxt", force)
    return {"data": data, "last_sync": last_sync}

# ---- DATA XE SỰ CỐ ----
@app.get("/api/xe-su-co", dependencies=[Depends(require_api_token)])
def get_xe_su_co(force: bool = False):
    data, last_sync = read_csv("xe_su_co", force)
    return {"data": data, "last_sync": last_sync}

# Cache for Google Maps coordinates
COORDS_CACHE_FILE = os.path.join(BASE_DIR, "scratch", "coords_cache.json")
_COORDS_CACHE = {}

def load_coords_cache():
    global _COORDS_CACHE
    if os.path.exists(COORDS_CACHE_FILE):
        try:
            if os.path.getsize(COORDS_CACHE_FILE) > 0:
                with open(COORDS_CACHE_FILE, "r", encoding="utf-8") as f:
                    _COORDS_CACHE = json.load(f)
                    print(f"[CACHE] Loaded {len(_COORDS_CACHE)} resolved coordinates from cache.")
                    return _COORDS_CACHE
        except Exception as e:
            print(f"[CACHE] Error loading coords cache: {e}")
    _COORDS_CACHE = {}
    return _COORDS_CACHE

def save_coords_cache():
    try:
        os.makedirs(os.path.dirname(COORDS_CACHE_FILE), exist_ok=True)
        with open(COORDS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_COORDS_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE] Error saving coords cache: {e}")

load_coords_cache()

def get_coords_from_url(url: str):
    if not url: return None
    import re
    import urllib.parse
    url = urllib.parse.unquote(url)
    
    # 1. @lat,lng
    m = re.search(r'@([-\d.]+),([-\d.]+)', url)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    # 2. !3dlat!4dlng
    m = re.search(r'!3d([-\d.]+)!4d([-\d.]+)', url)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    # 3. general lat,lng (e.g. search/16.407685,+107.589266)
    m = re.search(r'([-\d\.]+),\s*\+?([-\d\.]+)', url)
    if m:
        try:
            lat = float(m.group(1))
            lng = float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return [lat, lng]
        except ValueError:
            pass
    return None

def resolve_and_get_coords(url: str):
    if not url: return None
    if url in _COORDS_CACHE:
        return _COORDS_CACHE[url]
    
    # Try resolving redirect
    final_url = url
    if "maps.app.goo.gl" in url or "goo.gl/maps" in url:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                final_url = response.geturl()
        except Exception as e:
            print(f"[COORD] Error resolving short url {url}: {e}")
            
    coords = get_coords_from_url(final_url)
    _COORDS_CACHE[url] = coords
    save_coords_cache()
    return coords

# ---- DATA KHO GXT ----
def get_kho_gxt_xlsx_fallback():
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
    import urllib.request
    import zipfile
    import io
    import xml.etree.ElementTree as ET
    
    try:
        req = urllib.request.Request(xlsx_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            file_bytes = response.read()
            
        zip_file = zipfile.ZipFile(io.BytesIO(file_bytes))
        file_list = zip_file.namelist()
        
        # 1. Parse workbook.xml
        wb_data = zip_file.read("xl/workbook.xml")
        wb_root = ET.fromstring(wb_data)
        
        ns = {
            'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        }
        
        sheet_r_id = None
        for sheet in wb_root.findall('.//main:sheet', ns):
            name = sheet.get('name')
            if name == "Kho Giao Hàng Nặng":
                sheet_r_id = sheet.get(f"{{{ns['r']}}}id")
                break
                
        if not sheet_r_id:
            return None
            
        # 2. Get worksheet path
        rels_data = zip_file.read("xl/_rels/workbook.xml.rels")
        rels_root = ET.fromstring(rels_data)
        
        sheet_file = None
        rel_ns = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        for rel in rels_root.findall('.//rel:Relationship', rel_ns):
            if rel.get('Id') == sheet_r_id:
                target = rel.get('Target')
                sheet_file = f"xl/{target}"
                break
                
        if not sheet_file:
            return None
            
        # 3. Read sharedStrings
        shared_strings = []
        if "xl/sharedStrings.xml" in file_list:
            ss_data = zip_file.read("xl/sharedStrings.xml")
            ss_root = ET.fromstring(ss_data)
            for t in ss_root.findall('.//main:t', ns):
                shared_strings.append(t.text or "")
                
        # 4. Parse worksheet XML
        ws_data = zip_file.read(sheet_file)
        ws_root = ET.fromstring(ws_data)
        
        # 5. Parse worksheet rels for hyperlinks
        ws_rels_path = f"xl/worksheets/_rels/{os.path.basename(sheet_file)}.rels"
        hyperlink_map = {}
        if ws_rels_path in file_list:
            ws_rels_data = zip_file.read(ws_rels_path)
            ws_rels_root = ET.fromstring(ws_rels_data)
            for rel in ws_rels_root.findall('.//rel:Relationship', rel_ns):
                r_id = rel.get('Id')
                target_url = rel.get('Target')
                hyperlink_map[r_id] = target_url
                
        cell_hyperlinks = {}
        for hl in ws_root.findall('.//main:hyperlink', ns):
            ref = hl.get('ref')
            r_id = hl.get(f"{{{ns['r']}}}id")
            if r_id in hyperlink_map:
                cell_hyperlinks[ref] = hyperlink_map[r_id]
                
        # 6. Parse cells
        rows_data = []
        for row in ws_root.findall('.//main:row', ns):
            row_idx = row.get('r')
            row_cells = {}
            for cell in row.findall('./main:c', ns):
                ref = cell.get('r')
                cell_type = cell.get('t', '')
                val_elem = cell.find('./main:v', ns)
                val = val_elem.text if val_elem is not None else ""
                
                if cell_type == 's' and val:
                    idx = int(val)
                    cell_val = shared_strings[idx] if idx < len(shared_strings) else ""
                else:
                    cell_val = val
                    
                h_link = cell_hyperlinks.get(ref, "")
                row_cells[ref] = {
                    'value': cell_val,
                    'hyperlink': h_link
                }
            rows_data.append((row_idx, row_cells))
            
        if not rows_data:
            return None
            
        header_cells = rows_data[0][1]
        headers = {}
        for ref, cell in header_cells.items():
            col_letter = "".join([c for c in ref if c.isalpha()])
            headers[col_letter] = cell['value']
            
        col_map = {}
        for col_letter, h_name in headers.items():
            h_clean = h_name.strip()
            col_map[h_clean] = col_letter
            
        def get_cell_by_header(row_cells, header_name, row_num):
            col_letter = col_map.get(header_name)
            if not col_letter:
                return "", ""
            cell_ref = f"{col_letter}{row_num}"
            cell = row_cells.get(cell_ref)
            if not cell:
                return "", ""
            return cell['value'], cell['hyperlink']
            
        output = []
        for r_num, row_cells in rows_data[1:]:
            id_kho, _ = get_cell_by_header(row_cells, "ID Kho", r_num)
            if id_kho:
                id_kho = id_kho.strip()
                if "E" in id_kho or "e" in id_kho or "." in id_kho:
                    try:
                        id_kho = str(int(float(id_kho)))
                    except ValueError:
                        pass
                        
            if not id_kho:
                continue
                
            ten_kho, _ = get_cell_by_header(row_cells, "Tên Kho GXT", r_num)
            dia_chi, _ = get_cell_by_header(row_cells, "Địa chỉ kho", r_num)
            if not dia_chi:
                dia_chi = "Chưa có địa chỉ"
                
            _, link_ggm = get_cell_by_header(row_cells, "Link GGM", r_num)
            if not link_ggm:
                val_ggm, _ = get_cell_by_header(row_cells, "Link GGM", r_num)
                if val_ggm and val_ggm.lower().strip().startswith("http"):
                    link_ggm = val_ggm.strip()
                    
            if link_ggm:
                link_ggm = link_ggm.strip()
                if link_ggm and not link_ggm.lower().startswith("http"):
                    if "maps" in link_ggm.lower() or "google" in link_ggm.lower() or "goo.gl" in link_ggm.lower():
                        link_ggm = "https://" + link_ggm
                        
            vung, _ = get_cell_by_header(row_cells, "Vùng", r_num)
            tinh, _ = get_cell_by_header(row_cells, "Tỉnh", r_num)
            tinh_trang, _ = get_cell_by_header(row_cells, "Tình trạng", r_num)
            
            dien_tich, _ = get_cell_by_header(row_cells, "Diện Tích", r_num)
            if not dien_tich:
                dien_tich, _ = get_cell_by_header(row_cells, "Diện tích", r_num)
            if dien_tich:
                dien_tich = dien_tich.strip()
                if "." in dien_tich:
                    dien_tich = dien_tich.split(".")[0]
            else:
                dien_tich = ""
                
            ten_quan_ly, _ = get_cell_by_header(row_cells, "Tên", r_num)
            so_dien_thoai, _ = get_cell_by_header(row_cells, "Số điện thoại", r_num)
            
            coords = resolve_and_get_coords(link_ggm) if link_ggm else None
            mapStatus = "Đã hiển thị trên bản đồ" if (link_ggm and coords) else ("Có link, chưa lấy được vị trí" if link_ggm else "Chưa có link")
            
            output.append({
                # Original Vietnamese keys for "Kho GXT" compatibility
                "ID Kho": id_kho,
                "Tên": ten_quan_ly or "",
                "Số điện thoại": so_dien_thoai or "",
                "Tên Kho GXT": ten_kho or "",
                "Tỉnh": tinh or "",
                "Diện Tích": dien_tich,
                "Tình trạng": tinh_trang or "",
                "Địa chỉ kho": dia_chi,
                "Link GGM": link_ggm or "",
                "Vùng": vung or "",
                
                # New camelCase / snake_case keys
                "id_kho": id_kho,
                "idKho": id_kho,
                "ten_kho": ten_kho,
                "tenKho": ten_kho,
                "dia_chi": dia_chi,
                "diaChi": dia_chi,
                "link_ggm": link_ggm,
                "linkGGM": link_ggm,
                "googleMapsLink": link_ggm,
                "vung": vung,
                "tinh": tinh,
                "tinh_trang": tinh_trang,
                "dien_tich": dien_tich,
                "dienTich": dien_tich,
                "coords": coords,
                "mapStatus": mapStatus
            })
            
        return output
    except Exception as e:
        print(f"[XLSX FALLBACK ERROR] Failed to parse XLSX: {e}")
        return None

# ---- DATA KHO GXT ----
@app.get("/api/kho-gxt", dependencies=[Depends(require_api_token)])
def get_kho_gxt(force: bool = False):
    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
    output = None
    read_method = "unknown"
    headers_detected = []
    first_5_k_vals = []
    
    # 1. Thử dùng Google Sheets API qua Service Account
    if os.path.exists(sa_path):
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            
            creds = Credentials.from_service_account_file(
                sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            service = build("sheets", "v4", credentials=creds)
            
            result = service.spreadsheets().get(
                spreadsheetId=SHEET_ID,
                ranges=["Kho Giao Hàng Nặng!A1:M100"],
                fields="sheets(data(rowData(values(hyperlink,formattedValue))))"
            ).execute()
            
            sheets = result.get("sheets", [])
            if sheets:
                data_rows = sheets[0].get("data", [])[0].get("rowData", [])
                headers = [col.get("formattedValue", "") for col in data_rows[0].get("values", [])]
                headers_detected = headers
                
                id_kho_idx = headers.index("ID Kho") if "ID Kho" in headers else -1
                ten_kho_idx = headers.index("Tên Kho GXT") if "Tên Kho GXT" in headers else -1
                dia_chi_idx = headers.index("Địa chỉ kho") if "Địa chỉ kho" in headers else -1
                link_ggm_idx = headers.index("Link GGM") if "Link GGM" in headers else -1
                vung_idx = headers.index("Vùng") if "Vùng" in headers else -1
                tinh_idx = headers.index("Tỉnh") if "Tỉnh" in headers else -1
                tinh_trang_idx = headers.index("Tình trạng") if "Tình trạng" in headers else -1
                dien_tich_idx = headers.index("Diện Tích") if "Diện Tích" in headers else (headers.index("Diện tích") if "Diện tích" in headers else -1)
                ten_idx = headers.index("Tên") if "Tên" in headers else -1
                sdt_idx = headers.index("Số điện thoại") if "Số điện thoại" in headers else -1
                
                output = []
                for row_num, row in enumerate(data_rows[1:]):
                    values = row.get("values", [])
                    if not values or not any(v.get("formattedValue") for v in values):
                        continue
                    
                    id_kho = values[id_kho_idx].get("formattedValue", "") if len(values) > id_kho_idx and id_kho_idx != -1 else ""
                    ten_kho = values[ten_kho_idx].get("formattedValue", "") if len(values) > ten_kho_idx and ten_kho_idx != -1 else ""
                    dia_chi = values[dia_chi_idx].get("formattedValue", "Chưa có địa chỉ") if len(values) > dia_chi_idx and dia_chi_idx != -1 else "Chưa có địa chỉ"
                    if not dia_chi:
                        dia_chi = "Chưa có địa chỉ"
                    
                    vung = values[vung_idx].get("formattedValue", "") if len(values) > vung_idx and vung_idx != -1 else ""
                    tinh = values[tinh_idx].get("formattedValue", "") if len(values) > tinh_idx and tinh_idx != -1 else ""
                    tinh_trang = values[tinh_trang_idx].get("formattedValue", "") if len(values) > tinh_trang_idx and tinh_trang_idx != -1 else ""
                    
                    dien_tich = values[dien_tich_idx].get("formattedValue", "") if len(values) > dien_tich_idx and dien_tich_idx != -1 else ""
                    if dien_tich:
                        dien_tich = dien_tich.strip()
                        if "." in dien_tich:
                            dien_tich = dien_tich.split(".")[0]
                    else:
                        dien_tich = ""
                        
                    ten_quan_ly = values[ten_idx].get("formattedValue", "") if len(values) > ten_idx and ten_idx != -1 else ""
                    so_dien_thoai = values[sdt_idx].get("formattedValue", "") if len(values) > sdt_idx and sdt_idx != -1 else ""
                    
                    link_cell = values[link_ggm_idx] if len(values) > link_ggm_idx and link_ggm_idx != -1 else {}
                    link_ggm = link_cell.get("hyperlink", "")
                    if not link_ggm:
                        val = link_cell.get("formattedValue", "")
                        if val and val.lower().strip().startswith("http"):
                            link_ggm = val.strip()
                    
                    if row_num < 5:
                        first_5_k_vals.append(link_ggm or link_cell.get("formattedValue", ""))
                    
                    if link_ggm:
                        link_ggm = link_ggm.strip()
                        if link_ggm and not link_ggm.lower().startswith("http"):
                            if "maps" in link_ggm.lower() or "google" in link_ggm.lower() or "goo.gl" in link_ggm.lower():
                                link_ggm = "https://" + link_ggm
                    
                    coords = resolve_and_get_coords(link_ggm) if link_ggm else None
                    mapStatus = "Đã hiển thị trên bản đồ" if (link_ggm and coords) else ("Có link, chưa lấy được vị trí" if link_ggm else "Chưa có link")
                    
                    output.append({
                        "ID Kho": id_kho,
                        "Tên": ten_quan_ly or "",
                        "Số điện thoại": so_dien_thoai or "",
                        "Tên Kho GXT": ten_kho or "",
                        "Tỉnh": tinh or "",
                        "Diện Tích": dien_tich,
                        "Tình trạng": tinh_trang or "",
                        "Địa chỉ kho": dia_chi,
                        "Link GGM": link_ggm or "",
                        "Vùng": vung or "",
                        
                        "id_kho": id_kho,
                        "idKho": id_kho,
                        "ten_kho": ten_kho,
                        "tenKho": ten_kho,
                        "dia_chi": dia_chi,
                        "diaChi": dia_chi,
                        "link_ggm": link_ggm,
                        "linkGGM": link_ggm,
                        "googleMapsLink": link_ggm,
                        "vung": vung,
                        "tinh": tinh,
                        "tinh_trang": tinh_trang,
                        "dien_tich": dien_tich,
                        "dienTich": dien_tich,
                        "coords": coords,
                        "mapStatus": mapStatus
                    })
                read_method = "Google Sheets API"
        except Exception as e:
            print(f"[API ERROR] Error fetching sheet via Sheets API: {e}")
            
    # 2. Thử dùng public XLSX fallback (chứa hyperlink gốc)
    if not output:
        print("[FALLBACK] Attempting XLSX public parsing fallback...")
        try:
            output = get_kho_gxt_xlsx_fallback()
            if output:
                read_method = "Public XLSX Parser"
                headers_detected = ["ID Kho", "ID", "Tên", "Số điện thoại", "Tên Kho GXT", "Team Lead", "Vùng", "Tỉnh", "Diện Tích", "Địa chỉ kho", "Link GGM", "Tình trạng"]
                first_5_k_vals = [w.get("googleMapsLink", "") for w in output[:5]]
        except Exception as e:
            print(f"[FALLBACK ERROR] XLSX parsing failed: {e}")
            
    # 3. Thử dùng local JSON backup (cố định và có sẵn tọa độ gốc)
    if not output:
        backup_path = os.path.join(BASE_DIR, "scratch", "kho_gxt_backup.json")
        print(f"[FALLBACK] Attempting local JSON backup fallback from {backup_path}...")
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    output = json.load(f)
                if output:
                    read_method = "Local JSON Backup"
                    headers_detected = ["ID Kho", "Tên Kho GXT", "Địa chỉ kho", "Link GGM", "Diện Tích", "Vùng", "Tỉnh", "Tình trạng"]
                    first_5_k_vals = [w.get("googleMapsLink", "") for w in output[:5]]
            except Exception as e:
                print(f"[BACKUP ERROR] Failed to read backup file: {e}")
                
    # 4. Fallback cuối cùng: CSV thô (chỉ có chữ "Link")
    if not output:
        print("[FALLBACK] Attempting CSV fallback...")
        try:
            csv_rows, last_sync = read_csv("kho_gxt", force)
            output = []
            headers_detected = list(csv_rows[0].keys()) if csv_rows else []
            for row_num, r in enumerate(csv_rows):
                id_kho = (r.get("ID Kho") or "").strip()
                if id_kho:
                    if "." in id_kho:
                        id_kho = id_kho.split(".")[0]
                    if "E" in id_kho or "e" in id_kho:
                        try:
                            id_kho = str(int(float(id_kho)))
                        except ValueError:
                            pass
                            
                ten_kho = (r.get("Tên Kho GXT") or "").strip()
                dia_chi = (r.get("Địa chỉ kho") or "Chưa có địa chỉ").strip()
                if not dia_chi:
                    dia_chi = "Chưa có địa chỉ"
                    
                link_ggm = (r.get("Link GGM") or "").strip()
                if row_num < 5:
                    first_5_k_vals.append(link_ggm)
                    
                if link_ggm.lower() in ["", "#", "link"]:
                    link_ggm = ""
                    
                vung = (r.get("Vùng") or "").strip()
                tinh = (r.get("Tỉnh") or "").strip()
                tinh_trang = (r.get("Tình trạng") or "").strip()
                
                dien_tich = (r.get("Diện Tích") or r.get("Diện tích") or "").strip()
                if dien_tich:
                    if "." in dien_tich:
                        dien_tich = dien_tich.split(".")[0]
                else:
                    dien_tich = ""
                    
                ten_quan_ly = (r.get("Tên") or "").strip()
                so_dien_thoai = (r.get("Số điện thoại") or "").strip()
                    
                coords = resolve_and_get_coords(link_ggm) if link_ggm else None
                mapStatus = "Đã hiển thị trên bản đồ" if (link_ggm and coords) else ("Có link, chưa lấy được vị trí" if link_ggm else "Chưa có link")
                
                output.append({
                    "ID Kho": id_kho,
                    "Tên": ten_quan_ly or "",
                    "Số điện thoại": so_dien_thoai or "",
                    "Tên Kho GXT": ten_kho or "",
                    "Tỉnh": tinh or "",
                    "Diện Tích": dien_tich,
                    "Tình trạng": tinh_trang or "",
                    "Địa chỉ kho": dia_chi,
                    "Link GGM": link_ggm or "",
                    "Vùng": vung or "",
                    
                    "id_kho": id_kho,
                    "idKho": id_kho,
                    "ten_kho": ten_kho,
                    "tenKho": ten_kho,
                    "dia_chi": dia_chi,
                    "diaChi": dia_chi,
                    "link_ggm": link_ggm,
                    "linkGGM": link_ggm,
                    "googleMapsLink": link_ggm,
                    "vung": vung,
                    "tinh": tinh,
                    "tinh_trang": tinh_trang,
                    "dien_tich": dien_tich,
                    "dienTich": dien_tich,
                    "coords": coords,
                    "mapStatus": mapStatus
                })
            read_method = "CSV Fallback"
        except Exception as e:
            print(f"[CSV ERROR] CSV fallback failed: {e}")
            output = []

    # Bổ sung Debug bắt buộc theo Yêu cầu 6
    total_warehouses = len(output) if output else 0
    with_link = 0
    without_link = 0
    unparsed_coords = 0
    has_coords_count = 0
    
    if output:
        for w in output:
            link = w.get("googleMapsLink") or w.get("linkGGM") or w.get("link_ggm") or ""
            coords = w.get("coords")
            if link:
                with_link += 1
            else:
                without_link += 1
                
            if coords and len(coords) == 2:
                has_coords_count += 1
            else:
                unparsed_coords += 1
                
        print(f"\n===== [DEBUG KHO GXT] =====")
        print(f"Nguồn đọc: {read_method}")
        print(f"Sheet đang đọc: Kho Giao Hàng Nặng")
        print(f"Số dòng đọc được: {total_warehouses}")
        print(f"Header dòng đầu: {headers_detected}")
        print(f"Giá trị cột K của 5 dòng đầu: {first_5_k_vals}")
        print(f"Object sau khi parse của 5 kho đầu:")
        for idx, w in enumerate(output[:5]):
            print(f"  Kho {idx+1}:")
            print(f"    idKho: {w.get('idKho')}")
            print(f"    tenKho: {w.get('tenKho')}")
            print(f"    diaChi: {w.get('diaChi')}")
            print(f"    dienTich: {w.get('dienTich')}")
            print(f"    linkGGM: {w.get('linkGGM')}")
            print(f"    googleMapsLink: {w.get('googleMapsLink')}")
            print(f"    lat/lng: {w.get('coords')}")
            print(f"    mapStatus: {w.get('mapStatus')}")
        print(f"Số marker tạo được: {has_coords_count}")
        print(f"Số kho có link: {with_link}")
        print(f"Số kho không có link: {without_link}")
        print(f"Số kho không parse được tọa độ: {unparsed_coords}")
        print(f"===========================\n")
        
    return {"data": output or [], "last_sync": time.time()}

# ---- DATA ĐƠN TẠO N-1 ----

def compute_risk_alert_data(warnings_data, gtc_data, backlog_data, don_tao_data):
    # 1. Helper to clean warehouse name
    def short_kho(name):
        if not name: return ""
        name = str(name).strip()
        for prefix in ["Kho Giao Hàng Nặng - ", "Kho Giao Hàng Nặng ", "Kho ", "Bưu cục Giao Hàng Nặng - "]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip()

    # Helpers to parse float/int safely
    def parse_float(v, default=0.0):
        try:
            return float(str(v).replace(',', '.').replace('%', '').strip())
        except:
            return default

    def parse_int(v, default=0):
        try:
            return int(float(str(v).replace('.', '').replace(',', '').strip()))
        except:
            return default

    # 2. Group GTC by Warehouse
    gtc_by_kho = {}
    for r in gtc_data:
        kho = short_kho(r.get("Kho", ""))
        if not kho or kho == "--": continue
        if kho not in gtc_by_kho:
            gtc_by_kho[kho] = []
        gtc_by_kho[kho].append(r)

    # Calculate GTC metrics
    gtc_metrics = {}
    for kho, rows in gtc_by_kho.items():
        sorted_rows = sorted(rows, key=lambda x: x.get("Ngày", ""), reverse=True)
        latest_row = sorted_rows[0] if sorted_rows else {}
        latest_gtc = parse_float(latest_row.get("Tỉ lệ GTC", "0"))
        
        rows_7d = sorted_rows[:7]
        volumes = [parse_int(r.get("Số đơn GTC", r.get("success_volume", "0"))) for r in rows_7d]
        avg_gtc_7d = sum(volumes) / len(volumes) if volumes else 0.0
        max_gtc_7d = max(volumes) if volumes else 0
        
        if len(sorted_rows) >= 2:
            prev_rows = sorted_rows[1:8]
            prev_avg = sum(parse_float(r.get("Tỉ lệ GTC", "0")) for r in prev_rows) / len(prev_rows) if prev_rows else 0.0
            trend = latest_gtc - prev_avg
        else:
            trend = 0.0
            
        gtc_metrics[kho] = {
            "latest": latest_gtc,
            "avg7d": avg_gtc_7d,
            "max7d": max_gtc_7d,
            "maxGtcDon": max_gtc_7d,
            "trend": trend,
            "donTaoN1": 0
        }

    # 3. Process Don Tao N-1
    don_tao_by_kho = {}
    if don_tao_data:
        all_dates = sorted(list(set(str(r.get("Thời gian", r.get("time_view", ""))).split(" - ")[0] for r in don_tao_data if r.get("Thời gian") or r.get("time_view"))), reverse=True)
        latest_don_date = all_dates[0] if all_dates else ""
        for r in don_tao_data:
            d_str = str(r.get("Thời gian", r.get("time_view", ""))).split(" - ")[0]
            if d_str != latest_don_date: continue
            kho = short_kho(r.get("Kho giao", r.get("kho_giao", "")))
            if not kho or kho == "--": continue
            don = parse_int(r.get("Tổng đơn tạo", "0"))
            don_tao_by_kho[kho] = don_tao_by_kho.get(kho, 0) + don

    for kho, don in don_tao_by_kho.items():
        if kho in gtc_metrics:
            gtc_metrics[kho]["donTaoN1"] = don
        else:
            gtc_metrics[kho] = {
                "latest": 0.0, "avg7d": 0.0, "max7d": 0, "maxGtcDon": 0, "trend": 0.0,
                "donTaoN1": don
            }

    # 4. Group Backlog by Warehouse
    backlog_by_kho = {}
    if backlog_data:
        for r in backlog_data:
            kho = short_kho(r.get("Kho", ""))
            if not kho or kho == "--": continue
            lm = parse_int(r.get("Tồn giao (LM)", r.get("Backlog Last Mile", "0")))
            ktc = parse_int(r.get("Tồn KTC", "0"))
            backlog_by_kho[kho] = {"lm": lm, "ktc": ktc}

    # 5. Build riskForecast and overloadForecast
    risk_forecast = []
    overload_forecast = []
    
    for r in warnings_data:
        kho = short_kho(r.get("kho gxt", r.get("Kho", "")))
        if not kho or kho == "--": continue
        
        so_ngay = parse_float(r.get("Số ngày trở về ngày thường", r.get("Total ngày", "0")))
        status = r.get("Tình hình hiện tại", "Bình thường")
        next_status = r.get("Tình hình sắp tới", "Bình thường")
        
        gtc = gtc_metrics.get(kho, {"latest": 0.0, "avg7d": 0.0, "max7d": 0, "maxGtcDon": 0, "trend": 0.0, "donTaoN1": 0})
        bl = backlog_by_kho.get(kho, {"lm": 0, "ktc": 0})
        
        score = 0
        alerts = []
        recommendations = []
        
        if gtc["latest"] < 82 and gtc["latest"] > 0:
            score += 40
            alerts.append(f"GTC N-1 thấp ({gtc['latest']:.1f}%)")
            recommendations.append("Tăng cường giám sát tuyến giao, kiểm tra lý do thất bại")
        elif gtc["latest"] < 87 and gtc["latest"] > 0:
            score += 20
            alerts.append(f"GTC N-1 chưa đạt ({gtc['latest']:.1f}%)")
            recommendations.append("Rà soát NV có GTC thấp, hỗ trợ kỹ thuật giao nhận")
            
        if gtc["trend"] < -3:
            score += 25
            alerts.append(f"GTC đang giảm {abs(gtc['trend']):.1f}% so với TB tuần")
            recommendations.append("Điều tra nguyên nhân sụt giảm GTC trong 2-3 ngày gần đây")
        elif gtc["trend"] < -1:
            score += 10
            alerts.append("GTC có xu hướng giảm nhẹ")
            
        if bl["lm"] > 1000:
            score += 30
            alerts.append(f"Backlog LM nghiêm trọng ({bl['lm']:,})")
            recommendations.append("Tăng ca giao, bổ sung NV hỗ trợ kho, liên hệ điều phối khu vực")
        elif bl["lm"] > 500:
            score += 20
            alerts.append(f"Backlog LM cao ({bl['lm']:,})")
            recommendations.append("Ưu tiên xử lý đơn tồn lâu, phân phối lại tuyến giao")
        elif bl["lm"] > 200:
            score += 8
            alerts.append("Backlog LM ở mức trung bình")
            
        if bl["ktc"] > 500:
            score += 25
            alerts.append(f"Backlog KTC rất cao ({bl['ktc']:,})")
            recommendations.append("Kết hợp kho phụ, đẩy nhanh xử lý KTC tồn đọng")
        elif bl["ktc"] > 200:
            score += 15
            alerts.append(f"Backlog KTC cao ({bl['ktc']:,})")
            recommendations.append("Kiểm tra năng lực xử lý KTC, điều chỉnh lịch giao nhận")
            
        if status == "Nghiêm trọng" or so_ngay > 6:
            score += 30
            alerts.append(f"Đang ở trạng thái: {status} ({so_ngay}n)")
            recommendations.append("Báo cáo quản lý khu vực, lập kế hoạch phục hồi gấp")
        elif status in ["Bất ổn", "Cảnh báo"]:
            score += 15
            alerts.append(f"Trạng thái hiện tại: {status}")
            recommendations.append("Theo dõi chặt chẽ hàng ngày, chuẩn bị phương án dự phòng")
            
        if gtc["avg7d"] > 0 and gtc["avg7d"] < 85:
            score += 10
            alerts.append(f"GTC TB 7N thấp ({gtc['avg7d']:.1f}%)")
            
        max_gtc_don = gtc["maxGtcDon"]
        don_tao_n1 = gtc["donTaoN1"]
        if max_gtc_don > 0 and don_tao_n1 > 0 and don_tao_n1 > max_gtc_don * 1.5:
            ratio = don_tao_n1 / max_gtc_don
            score += 35
            alerts.append(f"⚠️ Hàng tạo cao gấp {ratio:.1f}x đơn GTC. Nguy cơ tồn hàng cao")
            recommendations.insert(0, f"🚛 Hàng tạo ({don_tao_n1:,}) cao gấp {ratio:.1f}x GTC max ngày ({max_gtc_don:,}). Kế hoạch chuẩn bị thêm xe tăng cường!")
        elif max_gtc_don > 0 and don_tao_n1 > 0 and don_tao_n1 > max_gtc_don * 1.2:
            ratio = don_tao_n1 / max_gtc_don
            score += 15
            alerts.append(f"⚠️ Hàng tạo cao gấp {ratio:.1f}x đơn GTC. Theo dõi sát nguy cơ tồn")
            recommendations.insert(0, f"📦 Hàng tạo ({don_tao_n1:,}) cao gấp {ratio:.1f}x GTC max ngày ({max_gtc_don:,}). Cần theo dõi sát.")
            
        if not recommendations:
            recommendations.append("Duy trì vận hành, tiếp tục giám sát định kỳ")
            
        risk_level = "good"
        risk_label = "🟢 Ổn định"
        if score >= 55:
            risk_level = "critical"
            risk_label = "🔴 Nghiêm trọng"
        elif score >= 30:
            risk_level = "warning"
            risk_label = "🟠 Cảnh báo"
        elif score >= 15:
            risk_level = "watch"
            risk_label = "🟡 Theo dõi"
            
        risk_forecast.append({
            "kho": kho,
            "score": score,
            "riskLevel": risk_level,
            "riskLabel": risk_label,
            "gtcN1": gtc["latest"],
            "gtcAvg7d": gtc["avg7d"],
            "gtcMax7d": gtc["max7d"],
            "gtcTrend": gtc["trend"],
            "blLm": bl["lm"],
            "blKtc": bl["ktc"],
            "alertsText": " | ".join(alerts) or "—",
            "recText": recommendations[0] if recommendations else "—"
        })
        
        # Overload forecast
        total_pressure = bl["lm"] + bl["ktc"] + don_tao_n1
        don_need_clear = total_pressure - gtc["latest"]
        overload_status = "stable"
        overload_label = "🟢 Bình thường"
        
        if total_pressure > max_gtc_don * 1.5:
            overload_status = "overloaded"
            overload_label = "🔴 Quá tải nặng"
        elif total_pressure > max_gtc_don * 1.2:
            overload_status = "risk"
            overload_label = "🟠 Nguy cơ"
        elif total_pressure > max_gtc_don * 0.9:
            overload_status = "watch"
            overload_label = "🟡 Theo dõi"
            
        action_recs = []
        if overload_status == "overloaded":
            action_recs.append("Yêu cầu bổ sung xe trung chuyển ngay trong ca tối.")
        elif overload_status == "risk":
            action_recs.append("Đề xuất xem xét tăng cường thêm tài xế/xe chạy tuyến.")
        else:
            action_recs.append("Tình trạng ổn định. Tiếp tục vận hành bình thường.")
            
        overload_forecast.append({
            "kho": kho,
            "overloadStatus": overload_status,
            "statusLabel": overload_label,
            "donTaoN1": don_tao_n1,
            "blLm": bl["lm"],
            "blKtc": bl["ktc"],
            "gtcN1Don": gtc["latest"],
            "donCanClear": max(0, int(don_need_clear)),
            "action": " ".join(action_recs)
        })

    risk_forecast = sorted(risk_forecast, key=lambda x: x["score"], reverse=True)

    # 6. Build n1VsGtcMax
    n1_vs_gtc_max = []
    all_khos = set(list(don_tao_by_kho.keys()) + list(gtc_metrics.keys()))
    for kho in all_khos:
        don_tao = don_tao_by_kho.get(kho, 0)
        gtc_max = gtc_metrics.get(kho, {}).get("max7d", 0)
        if not don_tao and not gtc_max: continue
        ratio = don_tao / gtc_max if gtc_max > 0 else 0.0
        
        level = "An toàn"
        if ratio > 1.5:
            level = "Tăng xe ngay"
        elif ratio > 1.2:
            level = "Theo dõi sát"
            
        n1_vs_gtc_max.append({
            "kho": kho,
            "donTao": don_tao,
            "gtcMax": gtc_max,
            "ratio": ratio,
            "level": level
        })
        
    n1_vs_gtc_max = sorted(n1_vs_gtc_max, key=lambda x: x["ratio"], reverse=True)

    # 7. Card metrics
    critical_count = sum(1 for r in risk_forecast if r["riskLevel"] == "critical")
    warning_count = sum(1 for r in risk_forecast if r["riskLevel"] == "warning")
    watch_count = sum(1 for r in risk_forecast if r["riskLevel"] == "watch")
    avg_days = sum(parse_float(r.get("Total ngày", "0")) for r in warnings_data) / len(warnings_data) if warnings_data else 0.0
    
    cards = {
        "critical": critical_count,
        "warning": warning_count,
        "watch": watch_count,
        "avgDays": round(avg_days, 1)
    }
    
    return {
        "currentStatus": warnings_data,
        "riskForecast": risk_forecast,
        "overloadForecast": overload_forecast,
        "n1VsGtcMax": n1_vs_gtc_max,
        "cards": cards
    }

@app.get("/api/don-tao", dependencies=[Depends(require_api_token)])
def get_don_tao(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("don_tao", force)
    if date:
        data = [r for r in data if r.get("Thời gian", r.get("time_view", "")).startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- DATA CẢNH BÁO ----
@app.get("/api/warnings", dependencies=[Depends(require_api_token)])
def get_warnings(force: bool = False):
    # Dùng chung logic của risk-alert để có đầy đủ debug log
    return get_risk_alert(force)

@app.get("/api/risk-alert", dependencies=[Depends(require_api_token)])
def get_risk_alert(force: bool = False):
    print("[API DEBUG] /api/risk-alert được gọi.")
    
    # 1. Đọc thô các nguồn
    backlog_data, _ = read_csv("backlog", force)
    gtc_data, _ = read_csv("gtc", force)
    don_tao_data, _ = read_csv("don_tao", force)
    warnings_data, last_sync = read_csv("warnings", force)
    
    # 2. Pre-compute 3 tab rủi ro
    result = compute_risk_alert_data(warnings_data, gtc_data, backlog_data, don_tao_data)
    
    # 3. Log debug bắt buộc theo Yêu cầu 6
    print(f"[API DEBUG] riskForecast count: {len(result['riskForecast'])}")
    print(f"[API DEBUG] overloadForecast count: {len(result['overloadForecast'])}")
    print(f"[API DEBUG] n1VsGtcMax count: {len(result['n1VsGtcMax'])}")
    print(f"[API DEBUG] Số dòng GTC đọc được: {len(gtc_data)}")
    print(f"[API DEBUG] Số dòng backlog đọc được: {len(backlog_data)}")
    print(f"[API DEBUG] Số dòng đơn tạo N-1 đọc được: {len(don_tao_data)}")
    
    total_kho = len(result["currentStatus"])
    print(f"[API DEBUG] Số kho sau khi merge: {total_kho}")
    
    # In 3 dòng dữ liệu mẫu cho mỗi tab
    print("[API DEBUG] 3 dòng dữ liệu mẫu của tab 'currentStatus':")
    for idx, w in enumerate(result["currentStatus"][:3]):
        print(f"  Dòng {idx+1}: Kho={w.get('kho gxt') or w.get('Kho')}, Status={w.get('Tình hình hiện tại')}, Days={w.get('Số ngày trở về ngày thường')}")
        
    print("[API DEBUG] 3 dòng dữ liệu mẫu của tab 'riskForecast':")
    for idx, w in enumerate(result["riskForecast"][:3]):
        print(f"  Dòng {idx+1}: Kho={w['kho']}, Score={w['score']}, Level={w['riskLabel']}, Coords GTC N-1={w['gtcN1']}%")
        
    print("[API DEBUG] 3 dòng dữ liệu mẫu của tab 'overloadForecast':")
    for idx, w in enumerate(result["overloadForecast"][:3]):
        print(f"  Dòng {idx+1}: Kho={w['kho']}, Status={w['statusLabel']}, N-1 Don={w['donTaoN1']}, Coords Need Clear={w['donCanClear']}")
        
    print("[API DEBUG] 3 dòng dữ liệu mẫu của tab 'n1VsGtcMax':")
    for idx, w in enumerate(result["n1VsGtcMax"][:3]):
        print(f"  Dòng {idx+1}: Kho={w['kho']}, N-1 Don={w['donTao']}, Max GTC 7D={w['gtcMax']}, Ratio={w['ratio']:.2f}")
        
    print(f"[API DEBUG] Cache key đang dùng: warnings")
    print(f"[API DEBUG] Thời gian cập nhật cache gần nhất: {last_sync}")
    
    if total_kho == 0:
        print("[API DEBUG WARNING] Tổng số kho sau khi merge = 0! Lý do: Data warnings rỗng.")
        
    # Trả về cấu trúc JSON chuẩn của risk-alert, đồng thời tương thích ngược bằng data
    return {
        "currentStatus": result["currentStatus"],
        "riskForecast": result["riskForecast"],
        "overloadForecast": result["overloadForecast"],
        "n1VsGtcMax": result["n1VsGtcMax"],
        "cards": result["cards"],
        "data": result["currentStatus"], # Compatibility link
        "last_sync": last_sync
    }

# ---- DASHBOARD OVERVIEW ----
@app.get("/api/dashboard/overview", dependencies=[Depends(require_api_token)])
def get_overview(force: bool = False):
    gtc_data, gtc_sync     = read_csv("gtc", force)
    b2b_data, _            = read_csv("b2b", force)
    backlog_data, _        = read_csv("backlog", force)
    ontime_data            = []
    returns_data, _        = read_csv("returns", force)
    ns_data, _             = read_csv("nang_suat", force)
    warning_data, warn_sync = read_csv("warnings", force)
    xe_data, _             = read_csv("xe_gxt", force)
    su_co_data, _          = read_csv("xe_su_co", force)
    kho_data, _            = read_csv("kho_gxt", force)
    pers_data, _           = read_csv("personnel", force)
    don_tao_data, _        = read_csv("don_tao", force)

    # Đơn Tạo N-1 latest day metrics
    dt_dates = sorted(set(r.get("Thời gian", r.get("time_view", "")).split(" - ")[0] for r in don_tao_data if r.get("Thời gian", r.get("time_view"))), reverse=True)
    dt_latest = dt_dates[0] if dt_dates else ""
    dt_latest_rows = [r for r in don_tao_data if r.get("Thời gian", r.get("time_view", "")).startswith(dt_latest)]
    
    total_don_tao = 0
    total_kg_tao = 0.0
    for r in dt_latest_rows:
        try:
            total_don_tao += int(str(r.get("Tổng đơn tạo", "0")).replace('.', '').replace(',', ''))
        except: pass
        try:
            total_kg_tao += float(str(r.get("Tổng khối lượng (KG)", "0")).replace(',', '.'))
        except: pass

    # Latest GTC date
    dates = sorted(set(r.get("Ngày", "") for r in gtc_data if r.get("Ngày")), reverse=True)
    latest_date = dates[0] if dates else ""
    latest_rows = [r for r in gtc_data if r.get("Ngày") == latest_date]

    total_don_gan = sum(int(r.get("Số đơn gán", 0) or 0) for r in latest_rows)
    total_don_gtc = sum(int(r.get("Số đơn GTC", 0) or 0) for r in latest_rows)
    avg_gtc = round((total_don_gtc / total_don_gan * 100), 2) if total_don_gan else 0

    # Avg Ontime (Không sử dụng dữ liệu Ontime)
    avg_ontime = "Không sử dụng dữ liệu Ontime"

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
    total_xe = 0
    for r in xe_data:
        # Hỗ trợ nhận diện cả tiêu đề cột chuẩn và tiêu đề cột bị lỗi font trong file CSV
        val = r.get("Tổng xe đang chạy") or r.get("Tá»•ng xe Ä‘ang cháº¡y") or r.get("Tổng xe") or 0
        try: total_xe += int(val or 0)
        except: pass

    # Total Kho GXT
    total_kho_gxt = len(kho_data)
    
    # Warning metrics (Sync with frontend logic)
    critical_count = 0
    unstable_count = 0
    upcoming_count = 0
    days_vals = []
    
    for r in warning_data:
        try:
            # 1. Critical if days > 6
            days = float(r.get("Số ngày trở về ngày thường") or r.get("Total ngày") or 0)
            if days > 6: critical_count += 1
            if days > 0: days_vals.append(days)
            
            # 2. Unstable if status is "Bất ổn"
            status = str(r.get("Tình hình hiện tại") or r.get("trạng thái hiện tại") or "").strip()
            if status == "Bất ổn": unstable_count += 1
            
            # 3. Upcoming if next status is warning/critical
            next_status = str(r.get("Dự báo sắp tới") or r.get("Tình hình sắp tới") or "").lower()
            if "cảnh báo" in next_status or "nghiêm trọng" in next_status:
                upcoming_count += 1
        except (ValueError, TypeError):
            pass
            
    avg_days = round(sum(days_vals) / len(days_vals), 1) if days_vals else 0

    # Total Personnel (Delivery Staff)
    total_delivery_staff = len([r for r in pers_data if str(r.get('Tên vị trí','')).strip().lower() == 'delivery staff'])

    return {
        "avg_gtc": avg_gtc,
        "latest_date": latest_date,
        "avg_ontime": avg_ontime,
        "total_backlog_7n": total_backlog,
        "total_b2b_priority": b2b_priority,
        "avg_fd_return": avg_fd,
        "avg_nang_suat": avg_nang_suat,
        "critical_warnings": critical_count,
        "unstable_warnings": unstable_count,
        "upcoming_warnings": upcoming_count,
        "avg_days_to_normal": avg_days,
        "total_backlog_lm": total_bl_lm,
        "total_backlog_ktc": total_bl_ktc,
        "total_backlog_all": total_bl_lm + total_bl_ktc,
        "total_xe_gxt": total_xe,
        "total_kho_gxt": total_kho_gxt,
        "total_personnel": total_delivery_staff,
        "total_don_tao": total_don_tao,
        "total_kg_tao": round(total_kg_tao, 2),
        "last_sync": max(gtc_sync, warn_sync)
    }

# ---- GTC BY KHO (latest date) ----
@app.get("/api/kpi/gtc/by-kho", dependencies=[Depends(require_api_token)])
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

# ---- TELEGRAM BOT DIAGNOSTICS (Admin only) ----
@app.get("/api/bot/status", dependencies=[Depends(require_admin_key)])
def get_bot_status():
    """Chỉ dành cho admin — trả về trạng thái tối thiểu, không lộ file/path."""
    try:
        try:
            from backend.telegram_bot import BOT_STATUS
        except ImportError:
            from telegram_bot import BOT_STATUS
            
        polling_disabled = os.environ.get("DISABLE_TELEGRAM_POLLING", "").lower() == "true"
        
        # Chỉ trả về thông tin cần thiết, KHÔNG lộ token/key/file listing
        return {
            "status": "success",
            "bot_running": BOT_STATUS.get("running", False),
            "initialized": BOT_STATUS.get("initialized", False),
            "last_error": BOT_STATUS.get("last_error"),
            "gemini_status": BOT_STATUS.get("gemini_status", "Unknown"),
            "polling_disabled": polling_disabled,
        }
    except Exception as e:
        return {"status": "error", "message": "Không thể lấy trạng thái Bot."}

@app.get("/api/bot/test-warning", dependencies=[Depends(require_admin_key)])
async def test_bot_warning(date: str = None):
    from datetime import datetime
    try:
        try:
            from backend.telegram_bot import generate_odo_warning_report
        except ImportError:
            from telegram_bot import generate_odo_warning_report

        target_date = date or datetime.now().strftime("%d/%m/%Y")
        report_msg = generate_odo_warning_report(target_date, "CHẨN ĐOÁN (TEST)")

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        warn_chat_id = os.environ.get("WARN_CHAT_ID", "")

        if not token:
            return {"status": "error", "message": "TELEGRAM_BOT_TOKEN chưa được cấu hình."}
        if not warn_chat_id:
            return {"status": "error", "message": "WARN_CHAT_ID chưa được cấu hình."}

        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": warn_chat_id,
                "text": report_msg,
                "parse_mode": "HTML"
            })

        if resp.status_code == 200:
            return {"status": "success", "message": f"Đã gửi test report cho ngày {target_date}."}
        else:
            return {"status": "error", "message": "Telegram API lỗi."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---- TELEGRAM REPORTING ----
import httpx
from datetime import datetime

# Cấu hình Telegram — tất cả lấy từ environment variables, không hardcode
TELEGRAM_TOKEN = None  # Chỉ dùng os.environ.get() bên dưới
CHAT_ID = None         # Chỉ dùng os.environ.get() bên dưới

import re as _re
def _sanitize_telegram_message(text: str) -> str:
    """
    Sanitize nội dung tin nhắn Telegram trước khi gửi:
    - Xóa Markdown link injection: [text](url) -> text
    - Giới hạn độ dài (Telegram limit: 4096 chars)
    """
    # Strip Markdown links: [anchor](url) -> anchor
    text = _re.sub(r'\[([^\]]{1,200})\]\(https?://[^\)]{1,500}\)', r'\1', text)
    # Xóa HTML injection cơ bản nếu dùng parse_mode=HTML
    # Đối với Markdown mode, giới hạn inline code block để tránh code injection
    return text[:4000].strip()

@app.post("/api/telegram/report", dependencies=[Depends(require_api_token)])
async def send_telegram_report(payload: dict):
    try:
        # Kiểm tra admin key trong payload (second layer)
        client_key = payload.get("key", "")
        if not _ADMIN_KEY or not secrets.compare_digest(client_key, _ADMIN_KEY):
            return {"status": "error", "message": "Bạn không có quyền thực hiện hành động này."}

        raw_message = payload.get("message", "")
        if not raw_message:
            return {"status": "error", "message": "Nội dung báo cáo trống."}

        # Sanitize trước khi gửi — chống Markdown injection
        message = _sanitize_telegram_message(raw_message)

        # Gửi qua Telegram API — chỉ dùng environment variables
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("WARN_CHAT_ID")
        if not token or not chat_id:
            return {"status": "error", "message": "Telegram chưa được cấu hình đúng."}
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
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


# =====================================================================
# XE VẬN HÀNH DAILY — CRUD APIs
# =====================================================================

XE_DAILY_DATA_FILE = os.path.join(BASE_DIR, "scratch", "xe_van_hanh_daily.json")
XE_DAILY_BACKUP_FILE = os.path.join(BASE_DIR, "scratch", "xe_van_hanh_daily_backup.json")

def _flex_get(row: dict, keys: list, default: str = ""):
    """Helper tìm value trong dict bất kể hoa thường, dấu tiếng Việt hoặc mojibake."""
    if not isinstance(row, dict):
        return default
    for k in keys:
        k_lower = k.lower().strip()
        for rk, rv in row.items():
            if not rk: continue
            if k_lower in str(rk).lower().strip():
                val = str(rv).strip()
                if val: return val
    return default

def _load_xe_daily_from_google_sheets():
    """Tải dữ liệu xe daily đã được lưu ở tab 'Xe Daily Logs' trên Google Sheets (nếu có)."""
    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
    if not os.path.exists(sa_path):
        return []
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        res = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range="Xe Daily Logs!A1:Z2000"
        ).execute()
        rows = res.get("values", [])
        if not rows or len(rows) < 2:
            return []
        
        headers = [str(h).strip().lower() for h in rows[0]]
        records = []
        for r in rows[1:]:
            if not r or not any(r): continue
            row_dict = {headers[i]: str(r[i]).strip() for i in range(min(len(headers), len(r)))}
            rec_id = row_dict.get("id") or secrets.token_hex(8)
            ngay = row_dict.get("ngày") or row_dict.get("ngay") or ""
            kho = row_dict.get("tên kho") or row_dict.get("kho") or ""
            loai = row_dict.get("loại") or row_dict.get("loai") or "Xe không hoạt động"
            sl = row_dict.get("số lượng xe") or row_dict.get("so_luong_xe") or "1"
            bien = row_dict.get("biển số xe") or row_dict.get("bien_so_xe") or "Xe OFF"
            ncc = row_dict.get("tên ncc") or row_dict.get("ncc") or "GHN Partner"
            tt = row_dict.get("trọng tải") or row_dict.get("trong_tai") or "1900"
            note = row_dict.get("ghi chú") or row_dict.get("ghi_chu") or ""
            nguoi = row_dict.get("người nhập") or row_dict.get("nguoi_nhap") or "Hệ thống"
            time_str = row_dict.get("thời gian ghi nhận") or row_dict.get("thoi_gian_ghi_nhan") or ""

            if ngay and kho:
                try: sl_num = int(sl)
                except: sl_num = 1
                try: tt_num = int(str(tt).replace(",", ""))
                except: tt_num = 1900

                records.append({
                    "id": rec_id,
                    "ngay": ngay,
                    "ten_kho": kho,
                    "loai": loai,
                    "so_luong_xe": sl_num,
                    "bien_so_xe": bien,
                    "ten_ncc": ncc,
                    "trong_tai": tt_num,
                    "ghi_chu": note,
                    "nguoi_nhap": nguoi,
                    "thoi_gian_ghi_nhan": time_str,
                })
        print(f"[XE DAILY] Recovered {len(records)} records from Google Sheets tab 'Xe Daily Logs'.")
        return records
    except Exception as e:
        print(f"[XE DAILY] Sheets read skipped: {e}")
        return []

def _is_july_2026_or_newer(date_str: str) -> bool:
    """Kiểm tra ngày có thuộc từ 01/07/2026 trở về sau hay không."""
    if not date_str: return False
    s = date_str.strip()
    parts = s.split("/") if "/" in s else s.split("-")
    if len(parts) == 3:
        try:
            if "/" in s:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y > 2026 or (y == 2026 and m >= 7):
                return True
        except (ValueError, TypeError):
            pass
    return False

def _generate_initial_xe_daily_records():
    """Tự động tổng hợp dữ liệu lịch sử xe vận hành thực tế từ 01/07/2026 khi chưa có dữ liệu."""
    records = []
    
    # 1. Thử load dữ liệu đã sync từ tab 'Xe Daily Logs' trên Google Sheet
    gs_records = _load_xe_daily_from_google_sheets()
    if gs_records:
        records.extend([r for r in gs_records if _is_july_2026_or_newer(r.get("ngay"))])

    try:
        su_co, _ = read_csv("xe_su_co")

        # 2. Chuyển đổi dữ liệu xe không hoạt động thực tế từ 01/07/2026 từ sheet xe_su_co
        existing_keys = set((r["ngay"], r["ten_kho"].lower(), r["loai"], r["bien_so_xe"].lower()) for r in records)
        for item in su_co:
            ngay = _flex_get(item, ["ngày", "ngay", "date"])
            kho = _flex_get(item, ["kho"])
            bien = _flex_get(item, ["biển", "bien"]) or "Xe OFF"
            ncc = _flex_get(item, ["ncc"]) or "GHN Partner"
            loi = _flex_get(item, ["lỗi", "loi"])
            ct = _flex_get(item, ["nội dung", "noi dung", "chi tiết"])
            note = f"{loi}: {ct}" if loi and ct else (loi or ct)

            if ngay and kho and _is_july_2026_or_newer(ngay):
                key = (ngay, kho.lower(), "Xe không hoạt động", bien.lower())
                if key not in existing_keys:
                    existing_keys.add(key)
                    records.append({
                        "id": secrets.token_hex(8),
                        "ngay": ngay,
                        "ten_kho": kho,
                        "loai": "Xe không hoạt động",
                        "so_luong_xe": 1,
                        "bien_so_xe": bien,
                        "ten_ncc": ncc,
                        "trong_tai": 1900,
                        "ghi_chu": note,
                        "nguoi_nhap": "Hệ thống (Sheet)",
                        "thoi_gian_ghi_nhan": "2026-07-01T08:00:00Z",
                    })

        print(f"[XE DAILY INITIAL] Generated {len(records)} real historical records from July 2026.")
    except Exception as e:
        print(f"[XE DAILY INITIAL ERROR] {e}")

    return records

def _load_xe_daily_records():
    """Load xe vận hành daily records từ JSON file chính hoặc file backup tự động khôi phục."""
    try:
        os.makedirs(os.path.dirname(XE_DAILY_DATA_FILE), exist_ok=True)
        # 1. Thử load từ file chính
        if os.path.exists(XE_DAILY_DATA_FILE):
            with open(XE_DAILY_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data

        # 2. Thử khôi phục từ file backup nếu file chính bị trống/reset
        if os.path.exists(XE_DAILY_BACKUP_FILE):
            with open(XE_DAILY_BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    print(f"[XE DAILY RECOVERY] Auto-restored {len(data)} records from backup file.")
                    with open(XE_DAILY_DATA_FILE, "w", encoding="utf-8") as f_main:
                        json.dump(data, f_main, ensure_ascii=False, indent=2)
                    return data
    except Exception as e:
        print(f"[XE DAILY] Error loading records: {e}")

    # 3. Nếu chưa có dữ liệu nào hoặc dữ liệu rỗng, tự động khởi tạo dữ liệu lịch sử
    initial = _generate_initial_xe_daily_records()
    if initial:
        _save_xe_daily_records(initial)
    return initial

def _sync_xe_daily_to_google_sheets(new_records: list):
    """Background helper ghi nhận các record xe daily mới vào Google Sheets tab 'Xe Daily Logs'."""
    def _worker():
        sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
        if not os.path.exists(sa_path) or not new_records:
            return
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            creds = Credentials.from_service_account_file(
                sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            service = build("sheets", "v4", credentials=creds)
            
            res = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
            sheets = [s['properties']['title'] for s in res.get('sheets', [])]
            if "Xe Daily Logs" not in sheets:
                body = {
                    "requests": [{
                        "addSheet": {
                            "properties": {"title": "Xe Daily Logs"}
                        }
                    }]
                }
                service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
                headers = [["ID", "Ngày", "Tên Kho", "Loại", "Số lượng xe", "Biển số xe", "Tên NCC", "Trọng tải", "Ghi chú", "Người nhập", "Thời gian ghi nhận"]]
                service.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range="Xe Daily Logs!A1:K1",
                    valueInputOption="RAW",
                    body={"values": headers}
                ).execute()

            rows_to_append = []
            for r in new_records:
                rows_to_append.append([
                    r.get("id", ""),
                    r.get("ngay", ""),
                    r.get("ten_kho", ""),
                    r.get("loai", ""),
                    str(r.get("so_luong_xe", 1)),
                    r.get("bien_so_xe", ""),
                    r.get("ten_ncc", ""),
                    str(r.get("trong_tai", 1900)),
                    r.get("ghi_chu", ""),
                    r.get("nguoi_nhap", "Hệ thống"),
                    r.get("thoi_gian_ghi_nhan", ""),
                ])

            service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="Xe Daily Logs!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows_to_append}
            ).execute()
            print(f"[XE DAILY SYNC] Appended {len(rows_to_append)} records to Google Sheets 'Xe Daily Logs'.")
        except Exception as e:
            print(f"[XE DAILY SYNC ERROR] {e}")

    threading.Thread(target=_worker, daemon=True).start()

def _save_xe_daily_records(records: list):
    """Ghi xe vận hành daily records vào cả JSON file chính và backup file."""
    try:
        os.makedirs(os.path.dirname(XE_DAILY_DATA_FILE), exist_ok=True)
        with open(XE_DAILY_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        if records:
            with open(XE_DAILY_BACKUP_FILE, "w", encoding="utf-8") as f_bk:
                json.dump(records, f_bk, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[XE DAILY] Error saving records: {e}")
        return False


@app.get("/api/xe-van-hanh/meta", dependencies=[Depends(require_api_token)])
def get_xe_van_hanh_meta(force: bool = False):
    """
    Trả về danh sách kho (từ sheet Xe GXT) và danh sách NCC (từ sheet Xe GXT).
    Frontend dùng để populate dropdown kho và NCC trong form ghi nhận.
    """
    xe_data, _ = read_csv("xe_gxt", force)

    kho_set = []
    kho_seen = set()
    ncc_map: dict = {}   # { ten_kho: [ncc1, ncc2, ...] }
    ncc_all_set = set()

    for row in xe_data:
        ten_kho = (
            row.get("Tên Kho GXT") or row.get("Ten Kho GXT") or
            row.get("TÃªn Kho GXT") or row.get("Kho") or ""
        ).strip()
        ten_ncc = (
            row.get("Tên NCC") or row.get("Ten NCC") or
            row.get("TÃªn NCC") or ""
        ).strip()

        if ten_kho and ten_kho not in kho_seen:
            kho_set.append(ten_kho)
            kho_seen.add(ten_kho)

        if ten_ncc:
            ncc_all_set.add(ten_ncc)
            if ten_kho:
                if ten_kho not in ncc_map:
                    ncc_map[ten_kho] = []
                if ten_ncc not in ncc_map[ten_kho]:
                    ncc_map[ten_kho].append(ten_ncc)

    return {
        "kho_list": sorted(kho_set),
        "ncc_map": ncc_map,
        "ncc_all": sorted(ncc_all_set),
    }


@app.get("/api/xe-van-hanh/records", dependencies=[Depends(require_api_token)])
def get_xe_van_hanh_records(
    date: str = Query(None),
    kho: str = Query(None),
    ncc: str = Query(None),
    loai: str = Query(None),
):
    """
    Trả về danh sách bản ghi xe vận hành daily, có thể filter theo:
    - date: dd/mm/yyyy
    - kho: tên kho
    - ncc: tên NCC
    - loai: 'Xe tăng cường' | 'Xe không hoạt động'
    """
    records = _load_xe_daily_records()

    if date:
        records = [r for r in records if r.get("ngay", "") == date]
    if kho:
        records = [r for r in records if kho.lower() in r.get("ten_kho", "").lower()]
    if ncc:
        records = [r for r in records if ncc.lower() in r.get("ten_ncc", "").lower()]
    if loai:
        records = [r for r in records if r.get("loai", "") == loai]

    # Sort by thoi_gian_ghi_nhan desc
    records = sorted(records, key=lambda r: r.get("thoi_gian_ghi_nhan", ""), reverse=True)
    return {"data": records, "total": len(records)}


@app.post("/api/xe-van-hanh/records", dependencies=[Depends(require_api_token)])
async def save_xe_van_hanh_records(request: Request):
    """
    Lưu một hoặc nhiều bản ghi xe vận hành daily.
    Body: { "records": [ { ngay, ten_kho, loai, so_luong_xe, bien_so_xe, ten_ncc, trong_tai, ghi_chu? }, ... ] }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    new_items = payload.get("records", [])
    if not new_items or not isinstance(new_items, list):
        raise HTTPException(status_code=400, detail="Field 'records' is required and must be a non-empty list")

    REQUIRED_FIELDS = ["ngay", "ten_kho", "loai", "so_luong_xe", "bien_so_xe", "ten_ncc", "trong_tai"]
    VALID_LOAI = ["Xe tăng cường", "Xe không hoạt động"]

    saved = []
    existing = _load_xe_daily_records()
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for idx, item in enumerate(new_items):
        missing = [f for f in REQUIRED_FIELDS if not str(item.get(f, "")).strip()]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Dòng {idx+1}: Thiếu các trường bắt buộc: {', '.join(missing)}"
            )

        loai = str(item.get("loai", "")).strip()
        if loai not in VALID_LOAI:
            raise HTTPException(
                status_code=422,
                detail=f"Dòng {idx+1}: Loại ghi nhận không hợp lệ. Chỉ chấp nhận: {', '.join(VALID_LOAI)}"
            )

        try:
            so_luong_xe = int(item.get("so_luong_xe", 1))
            if so_luong_xe < 1 or so_luong_xe > 10:
                so_luong_xe = max(1, min(10, so_luong_xe))
        except (ValueError, TypeError):
            so_luong_xe = 1

        try:
            trong_tai = int(str(item.get("trong_tai", "0")).replace(",", "").strip())
        except (ValueError, TypeError):
            trong_tai = 0

        record = {
            "id": secrets.token_hex(8),
            "ngay": str(item.get("ngay", "")).strip(),
            "ten_kho": str(item.get("ten_kho", "")).strip(),
            "loai": loai,
            "so_luong_xe": so_luong_xe,
            "bien_so_xe": str(item.get("bien_so_xe", "")).strip(),
            "ten_ncc": str(item.get("ten_ncc", "")).strip(),
            "trong_tai": trong_tai,
            "ghi_chu": str(item.get("ghi_chu", "")).strip(),
            "nguoi_nhap": str(item.get("nguoi_nhap", "Manager")).strip()[:50],
            "thoi_gian_ghi_nhan": now_iso,
        }
        existing.append(record)
        saved.append(record)

    if _save_xe_daily_records(existing):
        _sync_xe_daily_to_google_sheets(saved)
        print(f"[XE DAILY] Saved {len(saved)} new records. Total: {len(existing)}")
        return {"status": "ok", "saved": len(saved), "data": saved}
    else:
        raise HTTPException(status_code=500, detail="Không thể lưu dữ liệu. Vui lòng thử lại.")


@app.post("/api/xe-van-hanh/records/{record_id}/delete", dependencies=[Depends(require_api_token)])
async def delete_xe_van_hanh_record(record_id: str):
    """Xóa một bản ghi xe vận hành daily theo ID."""
    records = _load_xe_daily_records()
    original_len = len(records)
    records = [r for r in records if r.get("id") != record_id]

    if len(records) == original_len:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi ID={record_id}")

    if _save_xe_daily_records(records):
        return {"status": "ok", "message": "Đã xóa bản ghi thành công."}
    else:
        raise HTTPException(status_code=500, detail="Không thể lưu dữ liệu sau khi xóa.")


@app.post("/api/xe-van-hanh/import", dependencies=[Depends(require_api_token)])
async def import_xe_van_hanh_records(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Import nhiều bản ghi xe vận hành daily từ file CSV (hoặc XLSX đã convert sang CSV).
    Validate từng dòng, kiểm tra trùng, lưu các dòng hợp lệ.
    Trả về: { status, saved, errors, duplicates, error_details }
    """
    import re as _re

    VALID_LOAI = ["Xe tăng cường", "Xe không hoạt động"]
    MIN_DATE = "2026-07-01"  # ISO so sánh được

    def _ddmmyyyy_to_iso(date_str: str):
        """Chuyển dd/mm/yyyy → YYYY-MM-DD để so sánh. Trả None nếu lỗi."""
        s = (date_str or "").strip()
        # Accept dd/mm/yyyy or dd-mm-yyyy
        m = _re.match(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$", s)
        if not m:
            return None
        d, mo, y = m.group(1), m.group(2), m.group(3)
        try:
            from datetime import date as _date
            dt = _date(int(y), int(mo), int(d))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    def _today_iso():
        from datetime import datetime, timezone, timedelta
        vn_now = datetime.now(timezone(timedelta(hours=7)))
        return vn_now.strftime("%Y-%m-%d")

    # ---- Read raw bytes ----
    raw_bytes = await file.read()
    filename = (file.filename or "").lower()

    # ---- Parse to rows ----
    rows = []
    parse_error = None

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        # Try openpyxl (xlsx) or xlrd (xls)
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not all_rows:
                return {"status": "error", "message": "File Excel rỗng."}
            header = [str(c).strip() if c is not None else "" for c in all_rows[0]]
            for r in all_rows[1:]:
                row_dict = {header[i]: (str(r[i]).strip() if r[i] is not None else "") for i in range(min(len(header), len(r)))}
                rows.append(row_dict)
        except ImportError:
            parse_error = "Server chưa cài openpyxl. Vui lòng upload file .csv."
        except Exception as e:
            parse_error = f"Không thể đọc file Excel: {e}"
    else:
        # CSV
        try:
            text = raw_bytes.decode("utf-8-sig")  # handles BOM
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("cp1258")
            except Exception:
                text = raw_bytes.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        try:
            rows = list(reader)
        except Exception as e:
            parse_error = f"Không thể đọc file CSV: {e}"

    if parse_error:
        return {"status": "error", "message": parse_error}

    if not rows:
        return {"status": "error", "message": "File không có dữ liệu (chỉ có header hoặc rỗng)."}

    # ---- Normalize column names (flexible mapping) ----
    COL_MAP = {
        "ngay":         ["ngày", "ngay", "date", "Ngày", "Ngay"],
        "ten_kho":      ["tên kho", "ten kho", "tenkho", "kho", "Tên kho", "Ten kho"],
        "loai":         ["loại ghi nhận", "loai ghi nhan", "loai", "Loại ghi nhận", "Loai ghi nhan"],
        "so_luong_xe":  ["số lượng xe", "so luong xe", "sl xe", "sl_xe", "Số lượng xe", "So luong xe"],
        "bien_so_xe":   ["biển số xe", "bien so xe", "biensoxe", "bien_so", "Biển số xe", "Bien so xe"],
        "ten_ncc":      ["tên ncc", "ten ncc", "ncc", "Tên NCC", "Ten NCC"],
        "trong_tai":    ["trọng tải", "trong tai", "trongtai", "Trọng tải", "Trong tai"],
    }

    def _find_col(row_keys, variants):
        row_keys_lower = [k.lower().strip() for k in row_keys]
        for v in variants:
            if v.lower().strip() in row_keys_lower:
                idx = row_keys_lower.index(v.lower().strip())
                return list(row_keys)[idx]
        return None

    if not rows:
        return {"status": "error", "message": "Không có dòng dữ liệu nào."}

    first_row_keys = list(rows[0].keys())
    col_refs = {field: _find_col(first_row_keys, variants) for field, variants in COL_MAP.items()}

    # Check required columns exist
    missing_cols = [f for f, c in col_refs.items() if c is None]
    if missing_cols:
        return {
            "status": "error",
            "message": f"File thiếu các cột bắt buộc: {', '.join(missing_cols)}. "
                       f"Các cột tìm thấy trong file: {', '.join(first_row_keys)}"
        }

    # ---- Load existing records for duplicate check ----
    existing = _load_xe_daily_records()
    dup_keys = set()
    for r in existing:
        dk = (
            str(r.get("ngay", "")).strip(),
            str(r.get("ten_kho", "")).strip().lower(),
            str(r.get("loai", "")).strip(),
            str(r.get("bien_so_xe", "")).strip().lower(),
            str(r.get("ten_ncc", "")).strip().lower(),
        )
        dup_keys.add(dk)

    # ---- Validate & collect ----
    today_iso = _today_iso()
    saved_records = []
    error_details = []
    duplicate_count = 0
    import_dup_keys = set()  # track within this import batch

    for i, row in enumerate(rows):
        row_num = i + 2  # 1-indexed, +1 for header
        err_list = []

        def get_col(field):
            col = col_refs.get(field)
            return row.get(col, "").strip() if col else ""

        raw_ngay    = get_col("ngay")
        raw_kho     = get_col("ten_kho")
        raw_loai    = get_col("loai")
        raw_sl      = get_col("so_luong_xe")
        raw_bien    = get_col("bien_so_xe")
        raw_ncc     = get_col("ten_ncc")
        raw_tt      = get_col("trong_tai")

        # Skip completely empty rows
        if not any([raw_ngay, raw_kho, raw_loai, raw_sl, raw_bien, raw_ncc, raw_tt]):
            continue

        # 1. Ngày
        if not raw_ngay:
            err_list.append("Thiếu ngày")
        else:
            iso = _ddmmyyyy_to_iso(raw_ngay)
            if iso is None:
                err_list.append(f"Sai định dạng ngày '{raw_ngay}' (cần dd/mm/yyyy)")
            elif iso < MIN_DATE:
                err_list.append(f"Ngày '{raw_ngay}' nhỏ hơn 01/07/2026")
            elif iso > today_iso:
                err_list.append(f"Ngày '{raw_ngay}' lớn hơn ngày hiện tại")
            else:
                raw_ngay = _re.sub(r"^(\d)[/\-]", r"0\1/", raw_ngay.replace("-", "/"))
                raw_ngay = _re.sub(r"/(\d)[/\-]", r"/0\1/", raw_ngay)
                # Normalize to dd/mm/yyyy
                parts = raw_ngay.replace("-", "/").split("/")
                raw_ngay = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"

        # 2. Tên kho
        if not raw_kho:
            err_list.append("Thiếu tên kho")

        # 3. Loại ghi nhận
        if not raw_loai:
            err_list.append("Thiếu loại ghi nhận")
        elif raw_loai not in VALID_LOAI:
            err_list.append(f"Loại ghi nhận '{raw_loai}' không hợp lệ (chỉ nhận: {', '.join(VALID_LOAI)})")

        # 4. Số lượng xe
        sl_xe = 1
        if not raw_sl:
            err_list.append("Thiếu số lượng xe")
        else:
            try:
                sl_xe = int(float(raw_sl))
                if sl_xe < 1 or sl_xe > 5:
                    err_list.append(f"Số lượng xe '{raw_sl}' phải từ 1 đến 5")
            except ValueError:
                err_list.append(f"Số lượng xe '{raw_sl}' không phải số nguyên")

        # 5. Biển số xe
        if not raw_bien:
            err_list.append("Thiếu biển số xe")

        # 6. Tên NCC
        if not raw_ncc:
            err_list.append("Thiếu tên NCC")

        # 7. Trọng tải
        trong_tai = 0
        if not raw_tt:
            err_list.append("Thiếu trọng tải")
        else:
            try:
                trong_tai = int(float(str(raw_tt).replace(",", "").strip()))
                if trong_tai <= 0:
                    err_list.append(f"Trọng tải '{raw_tt}' phải lớn hơn 0")
            except ValueError:
                err_list.append(f"Trọng tải '{raw_tt}' không phải số")

        if err_list:
            error_details.append({"row": row_num, "errors": err_list})
            continue

        # ---- Duplicate check ----
        dup_key = (
            raw_ngay.strip(),
            raw_kho.strip().lower(),
            raw_loai.strip(),
            raw_bien.strip().lower(),
            raw_ncc.strip().lower(),
        )
        if dup_key in dup_keys or dup_key in import_dup_keys:
            duplicate_count += 1
            continue
        import_dup_keys.add(dup_key)

        # ---- Build record ----
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {
            "id": secrets.token_hex(8),
            "ngay": raw_ngay,
            "ten_kho": raw_kho,
            "loai": raw_loai,
            "so_luong_xe": sl_xe,
            "bien_so_xe": raw_bien,
            "ten_ncc": raw_ncc,
            "trong_tai": trong_tai,
            "ghi_chu": "",
            "nguoi_nhap": "Import Excel",
            "thoi_gian_ghi_nhan": now_iso,
        }
        existing.append(record)
        saved_records.append(record)
        dup_keys.add(dup_key)

    # ---- Save ----
    if saved_records:
        if not _save_xe_daily_records(existing):
            raise HTTPException(status_code=500, detail="Không thể lưu dữ liệu sau khi import.")

    total_read = len(rows)
    print(f"[XE DAILY IMPORT] Read={total_read}, Saved={len(saved_records)}, Errors={len(error_details)}, Dups={duplicate_count}")

    return {
        "status": "ok",
        "total_read": total_read,
        "saved": len(saved_records),
        "errors": len(error_details),
        "duplicates": duplicate_count,
        "error_details": error_details,
    }
# =====================================================================
# LOGIN LOGS — CRUD APIs & GOOGLE SHEETS INTEGRATION
# =====================================================================

LOGIN_LOG_FILE = os.path.join(BASE_DIR, "scratch", "login_logs.json")

def _load_login_logs():
    """Load danh sách log đăng nhập từ file local JSON."""
    try:
        os.makedirs(os.path.dirname(LOGIN_LOG_FILE), exist_ok=True)
        if os.path.exists(LOGIN_LOG_FILE) and os.path.getsize(LOGIN_LOG_FILE) > 0:
            with open(LOGIN_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[LOGIN LOG] Error loading logs: {e}")
    return []

def _save_login_logs(logs: list):
    """Ghi danh sách log đăng nhập vào file local JSON."""
    try:
        os.makedirs(os.path.dirname(LOGIN_LOG_FILE), exist_ok=True)
        with open(LOGIN_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[LOGIN LOG] Error saving logs: {e}")
        return False

def _append_login_log_to_sheets(log_data: dict):
    """Đẩy log đăng nhập lên Google Sheet, tab Login Logs."""
    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
    if not os.path.exists(sa_path):
        print("[LOGIN LOG] Google Sheets key not found. Log local only.")
        return False
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)

        body = {
            'values': [
                [
                    log_data.get('ngay', ''),
                    log_data.get('thoi_gian', ''),
                    log_data.get('id_ghn', ''),
                    log_data.get('ho_ten', ''),
                    log_data.get('kho_phong_ban', ''),
                    log_data.get('so_lan_trong_ngay', 1),
                    log_data.get('loai_truy_cap', ''),
                    log_data.get('ip', ''),
                    log_data.get('user_agent', '')
                ]
            ]
        }

        try:
            service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="Login Logs!A:I",
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            print("[LOGIN LOG] Successfully written to Google Sheets.")
            return True
        except Exception as sheet_err:
            print(f"[LOGIN LOG] Append directly failed, trying to create tab 'Login Logs': {sheet_err}")
            try:
                batch_update_request = {
                    'requests': [
                        {
                            'addSheet': {
                                'properties': {
                                    'title': 'Login Logs'
                                }
                            }
                        }
                    ]
                }
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SHEET_ID,
                    body=batch_update_request
                ).execute()

                # Ghi headers
                header_body = {
                    'values': [
                        ['Ngày', 'Thời gian', 'ID GHN', 'Họ và Tên', 'Tên Kho / Phòng ban', 'Số lần đăng nhập trong ngày', 'Loại truy cập', 'IP', 'User Agent']
                    ]
                }
                service.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range="Login Logs!A1:I1",
                    valueInputOption="USER_ENTERED",
                    body=header_body
                ).execute()

                # Ghi dữ liệu dòng đầu
                service.spreadsheets().values().append(
                    spreadsheetId=SHEET_ID,
                    range="Login Logs!A:I",
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                print("[LOGIN LOG] Created tab and written to Google Sheets.")
                return True
            except Exception as create_err:
                print(f"[LOGIN LOG] Failed to auto-create and write to sheet: {create_err}")
                return False
    except Exception as e:
        print(f"[LOGIN LOG] Sheets API error: {e}")
        return False

@app.post("/api/login-logs", dependencies=[Depends(require_api_token)])
async def log_login(request: Request, payload: dict):
    """
    Ghi nhận log đăng nhập của user sau khi điền thông tin cá nhân.
    Hỗ trợ cả payload camelCase theo yêu cầu.
    """
    id_ghn = str(payload.get("idGHN") or payload.get("id_ghn") or "").strip()
    ho_ten = str(payload.get("fullName") or payload.get("ho_ten") or "").strip()
    kho_phong_ban = str(payload.get("warehouseOrDepartment") or payload.get("kho_phong_ban") or "").strip()
    
    access_type = str(payload.get("accessType") or payload.get("loai_truy_cap") or "normal").strip()
    loai_truy_cap = "Truy cập admin bằng key" if access_type in ["admin", "Truy cập admin bằng key"] else "Truy cập thường"

    if not id_ghn or not ho_ten or not kho_phong_ban:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đầy đủ thông tin cá nhân.")

    # Timezone Vietnam (UTC+7)
    from datetime import datetime, timezone, timedelta
    vn_now = datetime.now(timezone(timedelta(hours=7)))
    
    ngay_str = payload.get("loginDate") or vn_now.strftime("%d/%m/%Y")
    gio_str = payload.get("loginTime") or vn_now.strftime("%H:%M:%S")

    ip = request.client.host if request.client else "unknown"
    user_agent = payload.get("userAgent") or request.headers.get("User-Agent", "")

    logs = _load_login_logs()

    # Tính số lần đăng nhập
    same_day_logs = [l for l in logs if l.get("ngay") == ngay_str and str(l.get("id_ghn")) == id_ghn]
    so_lan = len(same_day_logs) + 1

    # Cập nhật số lần đăng nhập cho các dòng cũ của cùng ID trong ngày (để hiển thị thống kê chính xác)
    for l in logs:
        if l.get("ngay") == ngay_str and str(l.get("id_ghn")) == id_ghn:
            l["so_lan_trong_ngay"] = so_lan

    new_log = {
        "ngay": ngay_str,
        "thoi_gian": gio_str,
        "id_ghn": id_ghn,
        "ho_ten": ho_ten,
        "kho_phong_ban": kho_phong_ban,
        "so_lan_trong_ngay": so_lan,
        "loai_truy_cap": loai_truy_cap,
        "ip": ip,
        "user_agent": user_agent
    }

    logs.append(new_log)
    _save_login_logs(logs)

    # Đẩy lên Google Sheets
    _append_login_log_to_sheets(new_log)

    return {"status": "ok", "so_lan_trong_ngay": so_lan}

@app.get("/api/login-logs")
def get_login_logs(
    x_admin_key: str = Header(None),
    date: str = Query(None),
    id_ghn: str = Query(None),
    ho_ten: str = Query(None),
    kho_phong_ban: str = Query(None)
):
    """
    Trả về toàn bộ danh sách log đăng nhập phục vụ admin xem dashboard.
    Chỉ cho phép truy cập nếu X-Admin-Key khớp với key được yêu cầu.
    """
    is_admin = False
    # Validate key admin
    ADMIN_KEY_REQUIRED = "JnBjZUODMXhy7BCupcB5IMPwYOJfHuDkm1-OKR9Jklc"
    if x_admin_key:
        if x_admin_key == ADMIN_KEY_REQUIRED or (_ADMIN_KEY and secrets.compare_digest(x_admin_key, _ADMIN_KEY)):
            is_admin = True

    if not is_admin:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập dữ liệu này.")

    logs = _load_login_logs()

    # Áp dụng bộ lọc
    if date:
        logs = [l for l in logs if l.get("ngay") == date]
    if id_ghn:
        logs = [l for l in logs if id_ghn in str(l.get("id_ghn"))]
    if ho_ten:
        logs = [l for l in logs if ho_ten.lower() in str(l.get("ho_ten", "")).lower()]
    if kho_phong_ban:
        logs = [l for l in logs if kho_phong_ban.lower() in str(l.get("kho_phong_ban", "")).lower()]

    # Sắp xếp mới nhất trước (Ngày dạng dd/mm/yyyy, Giờ dạng hh:mm:ss)
    def _parse_log_datetime(item):
        try:
            d, m, y = item.get("ngay", "").split("/")
            h, mi, s = item.get("thoi_gian", "").split(":")
            from datetime import datetime
            return datetime(int(y), int(m), int(d), int(h), int(mi), int(s))
        except Exception:
            from datetime import datetime
            return datetime.min

    logs = sorted(logs, key=_parse_log_datetime, reverse=True)
    return {"data": logs, "total": len(logs)}


# ---- SERVE FRONTEND ----


if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    print(f"[STARTUP] StaticFiles mounted from {FRONTEND_DIR}")
else:
    print(f"[STARTUP] WARNING: frontend/ directory not found at {FRONTEND_DIR}")

def serve_utf8(filepath: str, media_type: str):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type=f"{media_type}; charset=utf-8")
    except Exception as e:
        print(f"[SERVE ERROR] Failed to read {filepath} as utf-8: {e}")
        return FileResponse(filepath, media_type=media_type)

@app.get("/app.js")
def read_js():
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    target = js_path if os.path.exists(js_path) else os.path.join(BASE_DIR, "app.js")
    return serve_utf8(target, "application/javascript")

@app.get("/styles.css")
def read_css():
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    target = css_path if os.path.exists(css_path) else os.path.join(BASE_DIR, "styles.css")
    return serve_utf8(target, "text/css")

@app.get("/ghn_logo.png")
@app.get("/static/ghn_logo.png")
def read_logo():
    logo_path = os.path.join(FRONTEND_DIR, "ghn_logo.png")
    target = logo_path if os.path.exists(logo_path) else os.path.join(BASE_DIR, "ghn_logo.png")
    return FileResponse(target, media_type="image/png")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    target = index_path if os.path.exists(index_path) else os.path.join(BASE_DIR, "index.html")
    if os.path.exists(target):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            return HTMLResponse(content=content)
        except Exception:
            return FileResponse(target)
    # Không trả về thông tin nhạy cảm về server
    return HTMLResponse(content="<h1>Service Unavailable</h1>", status_code=503)


# =====================================================================
# DASHBOARD BACKGROUND SYNC SCHEDULER & CACHE ENDPOINTS
# =====================================================================
DASHBOARD_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "dashboard_cache.json")
_IS_SYNCING = False

async def run_dashboard_sync_scheduler():
    """Background task chạy định kỳ mỗi 3 phút để tự động sync dữ liệu."""
    import asyncio
    print("[SCHEDULER] Kích hoạt Dashboard Background Sync Loop.")
    await asyncio.sleep(2)  # Đợi server khởi động ổn định
    while True:
        try:
            print("[SCHEDULER] Bắt đầu tự động đồng bộ dữ liệu dashboard...")
            await sync_dashboard_cache(force=False)
        except Exception as e:
            print(f"[SCHEDULER ERROR] Lỗi đồng bộ dashboard nền: {e}")
        await asyncio.sleep(180)  # Chạy mỗi 3 phút

async def sync_dashboard_cache(force=False):
    import asyncio
    global _IS_SYNCING
    if _IS_SYNCING:
        print("[SYNC] Một tiến trình đồng bộ khác đang chạy. Bỏ qua.")
        return False
        
    _IS_SYNCING = True
    try:
        from datetime import datetime, timezone, timedelta
        vn_now = datetime.now(timezone(timedelta(hours=7)))
        last_sync_str = vn_now.strftime("%H:%M:%S")
        
        start_time = time.time()
        
        # ĐỌC OLD CACHE TRƯỚC Ở ĐẦU để khôi phục khi xảy ra lỗi/rỗng
        old_cache = {}
        if os.path.exists(DASHBOARD_CACHE_PATH):
            try:
                with open(DASHBOARD_CACHE_PATH, "r", encoding="utf-8") as f:
                    old_cache = json.load(f)
            except: pass
            
        other_keys = [
            "gtc", "b2b", "backlog", "returns", "nang_suat", 
            "warnings", "xe_gxt", "xe_su_co", 
            "personnel", "don_tao", "gtc_b2b", "don_b2b", 
            "returns_by_client"
        ]
        
        key_map = {
            "gtc": "gtcData",
            "b2b": "b2bData",
            "backlog": "backlogData",
            "returns": "returnsData",
            "nang_suat": "nangSuatData",
            "warnings": "warningsData",
            "xe_gxt": "xeGxtData",
            "xe_su_co": "xeSuCoData",
            "personnel": "personnelData",
            "don_tao": "donTaoData",
            "gtc_b2b": "gtcB2bData",
            "don_b2b": "donB2bData",
            "returns_by_client": "returnsByClientData"
        }
        
        # Tạo tasks cho other sheets và get_kho_gxt
        tasks = [asyncio.to_thread(read_csv, key, force) for key in other_keys]
        tasks.append(asyncio.to_thread(get_kho_gxt, force))
        
        print(f"[SYNC] Bắt đầu đồng bộ song song {len(other_keys) + 1} sheets...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sheet_status = {}
        cached_data = {
            "ontimeData": []
        }
        
        for idx, key in enumerate(other_keys):
            res = results[idx]
            elapsed = time.time() - start_time
            mapped_key = key_map[key]
            
            # Check valid (không lỗi và không rỗng dòng)
            is_valid = True
            err_msg = ""
            if isinstance(res, Exception):
                is_valid = False
                err_msg = str(res)
            else:
                data, cache_time = res
                if not data or len(data) == 0:
                    is_valid = False
                    err_msg = "Dữ liệu trả về rỗng"
                    
            if not is_valid:
                print(f"[SYNC WARNING] Sheet {key} lỗi hoặc rỗng. Khôi phục từ old cache...")
                sheet_status[key] = {"success": False, "error": err_msg, "time": round(elapsed, 2)}
                
                # Khôi phục từ old cache nếu có dữ liệu tốt
                if old_cache and "data" in old_cache and mapped_key in old_cache["data"] and len(old_cache["data"][mapped_key]) > 0:
                    cached_data[mapped_key] = old_cache["data"][mapped_key]
                elif key in CACHE and len(CACHE[key]['data']) > 0:
                    cached_data[mapped_key] = CACHE[key]['data']
                else:
                    cached_data[mapped_key] = []
            else:
                data, cache_time = res
                sheet_status[key] = {"success": True, "time": round(elapsed, 2)}
                cached_data[mapped_key] = data
                
        # Xử lý kết quả get_kho_gxt ở cuối
        kho_res = results[-1]
        elapsed = time.time() - start_time
        
        is_kho_valid = True
        kho_err = ""
        if isinstance(kho_res, Exception):
            is_kho_valid = False
            kho_err = str(kho_res)
        else:
            kho_data = kho_res.get("data", [])
            if not kho_data or len(kho_data) == 0:
                is_kho_valid = False
                kho_err = "Kho data rỗng"
                
        if not is_kho_valid:
            print("[SYNC WARNING] get_kho_gxt lỗi hoặc rỗng. Khôi phục từ old cache...")
            sheet_status["kho_gxt"] = {"success": False, "error": kho_err, "time": round(elapsed, 2)}
            if old_cache and "data" in old_cache and "khoGxtData" in old_cache["data"] and len(old_cache["data"]["khoGxtData"]) > 0:
                cached_data["khoGxtData"] = old_cache["data"]["khoGxtData"]
            else:
                cached_data["khoGxtData"] = []
        else:
            cached_data["khoGxtData"] = kho_res.get("data", [])
            sheet_status["kho_gxt"] = {"success": True, "time": round(elapsed, 2)}
                
        # Tính toán overview
        try:
            # Gọi trực tiếp get_overview để tận dụng cache vừa fetch
            ov = get_overview(force=False)
            cached_data["overview"] = ov
        except Exception as ov_err:
            print(f"[SYNC ERROR] Lỗi pre-compute overview: {ov_err}")
            cached_data["overview"] = {}
            
        # Tính toán và lưu trữ computed risk-alert data vào cache (Yêu cầu 4 & 5)
        try:
            warnings_data = cached_data.get("warningsData", [])
            gtc_data = cached_data.get("gtcData", [])
            backlog_data = cached_data.get("backlogData", [])
            don_tao_data = cached_data.get("donTaoData", [])
            
            # Không ghi đè cache tốt bằng cache rỗng
            if warnings_data and len(warnings_data) > 0:
                risk_computed = compute_risk_alert_data(warnings_data, gtc_data, backlog_data, don_tao_data)
                cached_data["risk_alert_computed"] = risk_computed
                print("[SYNC] Đã tính toán và lưu pre-compute risk-alert data thành công.")
            else:
                if old_cache and "data" in old_cache and "risk_alert_computed" in old_cache["data"]:
                    cached_data["risk_alert_computed"] = old_cache["data"]["risk_alert_computed"]
                    print("[SYNC WARNING] WarningsData bị rỗng khi sync, đã khôi phục computed risk cũ từ old_cache.")
        except Exception as risk_err:
            print(f"[SYNC ERROR] Lỗi tính toán risk-alert data: {risk_err}")
            
        total_time = time.time() - start_time
        print(f"[SYNC COMPLETED] Hoàn thành đồng bộ toàn bộ dữ liệu dashboard trong {total_time:.2f}s.")
        
        final_cache = {
            "sync_info": {
                "last_sync": last_sync_str,
                "sheet_status": sheet_status,
                "total_sync_time": round(total_time, 2)
            },
            "data": cached_data
        }
        
        # Giữ lại cache cũ cho sheet nào lỗi/rỗng (Safety Double Check)
        if old_cache and "data" in old_cache:
            for key in key_map.keys():
                mapped_key = key_map[key]
                if not sheet_status[key]["success"] and mapped_key in old_cache["data"] and len(old_cache["data"][mapped_key]) > 0:
                    final_cache["data"][mapped_key] = old_cache["data"][mapped_key]
                    print(f"[SYNC FALLBACK] Giữ lại cache cũ của sheet lỗi: {key}")
                    
        os.makedirs(os.path.dirname(DASHBOARD_CACHE_PATH), exist_ok=True)
        with open(DASHBOARD_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(final_cache, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        print(f"[SYNC FATAL ERROR] Lỗi nghiêm trọng khi đồng bộ cache: {e}")
        return False
    finally:
        _IS_SYNCING = False

@app.get("/api/dashboard-cache", dependencies=[Depends(require_api_token)])
async def get_dashboard_cache():
    """API trả về toàn bộ dữ liệu dashboard đã cache sẵn từ đĩa."""
    if not os.path.exists(DASHBOARD_CACHE_PATH):
        print("[CACHE] Chưa có file cache đĩa, đang khởi động đồng bộ tức thì...")
        await sync_dashboard_cache(force=False)
        
    try:
        with open(DASHBOARD_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
            
        # Nếu có risk_alert_computed trong cache, giải nén các trường của nó ra ngoài data object
        # để client nhận được qua state (Yêu cầu 4)
        if cache and "data" in cache and "risk_alert_computed" in cache["data"]:
            r_comp = cache["data"]["risk_alert_computed"]
            cache["data"]["currentStatus"] = r_comp.get("currentStatus", [])
            cache["data"]["riskForecast"] = r_comp.get("riskForecast", [])
            cache["data"]["overloadForecast"] = r_comp.get("overloadForecast", [])
            cache["data"]["n1VsGtcMax"] = r_comp.get("n1VsGtcMax", [])
            cache["data"]["cards"] = r_comp.get("cards", {})
            
        return cache
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể đọc file cache: {str(e)}")

@app.post("/api/dashboard-cache/sync", dependencies=[Depends(require_api_token)])
async def force_dashboard_sync():
    """Yêu cầu force đồng bộ nền mới nhất ngay lập tức."""
    success = await sync_dashboard_cache(force=True)
    if success:
        return {"status": "ok", "message": "Đồng bộ hoàn tất thành công."}
    else:
        return {"status": "busy", "message": "Hệ thống đang bận đồng bộ dữ liệu nền. Vui lòng chờ."}
