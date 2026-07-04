import sys
import os
import io
import secrets
import time
import json
from collections import defaultdict

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

from fastapi import FastAPI, Query, Header, HTTPException, Depends, Request
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

app.add_middleware(SecurityHeadersMiddleware)

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

def read_csv(key: str, force: bool = False):
    gid = GIDS.get(key)
    if not gid: return [], 0
    
    now = time.time()
    # Check cache unless force is requested
    if not force and key in CACHE and (now - CACHE[key]['time']) < CACHE_TTL:
        return CACHE[key]['data'], CACHE[key]['time']
        
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
@app.get("/api/kho-gxt", dependencies=[Depends(require_api_token)])
def get_kho_gxt(force: bool = False):
    sa_path = os.path.join(BASE_DIR, "alien-oarlock-499610-a5-2d813b6cc71d.json")
    if os.path.exists(sa_path):
        try:
            import json
            import time
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
                
                id_kho_idx = headers.index("ID Kho") if "ID Kho" in headers else -1
                ten_kho_idx = headers.index("Tên Kho GXT") if "Tên Kho GXT" in headers else -1
                dia_chi_idx = headers.index("Địa chỉ kho") if "Địa chỉ kho" in headers else -1
                link_ggm_idx = headers.index("Link GGM") if "Link GGM" in headers else -1
                vung_idx = headers.index("Vùng") if "Vùng" in headers else -1
                tinh_idx = headers.index("Tỉnh") if "Tỉnh" in headers else -1
                tinh_trang_idx = headers.index("Tình trạng") if "Tình trạng" in headers else -1
                
                output = []
                for row in data_rows[1:]:
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
                    
                    link_cell = values[link_ggm_idx] if len(values) > link_ggm_idx and link_ggm_idx != -1 else {}
                    link_ggm = link_cell.get("hyperlink", "")
                    if not link_ggm:
                        val = link_cell.get("formattedValue", "")
                        if val and val.lower().strip().startswith("http"):
                            link_ggm = val.strip()
                    
                    if link_ggm:
                        link_ggm = link_ggm.strip()
                        if link_ggm and not link_ggm.lower().startswith("http"):
                            if "maps" in link_ggm.lower() or "google" in link_ggm.lower() or "goo.gl" in link_ggm.lower():
                                link_ggm = "https://" + link_ggm
                    
                    coords = resolve_and_get_coords(link_ggm) if link_ggm else None
                    
                    output.append({
                        "id_kho": id_kho,
                        "ten_kho": ten_kho,
                        "dia_chi": dia_chi,
                        "link_ggm": link_ggm,
                        "vung": vung,
                        "tinh": tinh,
                        "tinh_trang": tinh_trang,
                        "coords": coords
                    })
                
                return {"data": output, "last_sync": time.time()}
        except Exception as e:
            print(f"[API ERROR] Error fetching sheet via Sheets API: {e}")
            
    # Fallback to CSV
    csv_rows, last_sync = read_csv("kho_gxt", force)
    output = []
    for r in csv_rows:
        output.append({
            "id_kho": r.get("ID Kho", ""),
            "ten_kho": r.get("Tên Kho GXT", ""),
            "dia_chi": r.get("Địa chỉ kho", "Chưa có địa chỉ") or "Chưa có địa chỉ",
            "link_ggm": r.get("Link GGM", ""),
            "vung": r.get("Vùng", ""),
            "tinh": r.get("Tỉnh", ""),
            "tinh_trang": r.get("Tình trạng", ""),
            "coords": None
        })
    return {"data": output, "last_sync": last_sync}

# ---- DATA ĐƠN TẠO N-1 ----
@app.get("/api/don-tao", dependencies=[Depends(require_api_token)])
def get_don_tao(date: str = Query(None), force: bool = False):
    data, last_sync = read_csv("don_tao", force)
    if date:
        data = [r for r in data if r.get("Thời gian", r.get("time_view", "")).startswith(date)]
    return {"data": data, "last_sync": last_sync}

# ---- DATA CẢNH BÁO ----
@app.get("/api/warnings", dependencies=[Depends(require_api_token)])
def get_warnings(force: bool = False):
    data, last_sync = read_csv("warnings", force)
    return {"data": data, "last_sync": last_sync}

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

