"""
odo_scheduler.py
Scheduler bất đồng bộ cho BOT ODO — chạy cùng FastAPI qua asyncio.create_task()
Múi giờ: Asia/Ho_Chi_Minh
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import pytz

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ── Config từ env (dynamic getters) ─────────────────────────────────────────────
def get_odo_token() -> str:
    return os.environ.get("ODO_BOT_TOKEN", "").strip()

def get_odo_chat_id() -> str:
    return os.environ.get("ODO_CHAT_ID", "-1002712779761").strip()

def get_dashboard_url() -> str:
    return os.environ.get("DASHBOARD_BASE_URL", "https://ai-ghn-gxt.up.railway.app").strip().rstrip("/")

def get_odo_sheet_id() -> str:
    return os.environ.get("ODO_SPREADSHEET_ID", "1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo").strip()

def get_odo_sheet_name() -> str:
    return os.environ.get("ODO_SHEET_NAME", "Tháng 7").strip()


# ── In-memory state (backup cho JSON file) ────────────────────────────────────
_odo_state: Dict = {}           # { "YYYY-MM-DD|kho": { missing, expected, reported } }
_idempotency: Set[str] = set()  # { "odo_current_2026-07-22_1800", ... }
_xe_daily_sent: Optional[str] = None   # ngày đã gửi xe daily
_odo_bot_app = None             # telegram Application instance

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odo_state.json")


# ── State persistence ─────────────────────────────────────────────────────────

def _load_state():
    global _odo_state, _idempotency
    import json
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                d = json.load(f)
            _odo_state    = d.get("statuses", {})
            _idempotency  = set(d.get("idempotency", []))
            logger.info(f"[ODO State] Loaded: {len(_odo_state)} statuses, {len(_idempotency)} idem keys")
        except Exception as e:
            logger.error(f"[ODO State] Load error: {e}")


def _save_state():
    import json
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "statuses": _odo_state,
                "idempotency": list(_idempotency),
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[ODO State] Save error: {e}")


def _check_idem(key: str) -> bool:
    return key in _idempotency


def _set_idem(key: str):
    _idempotency.add(key)
    _save_state()


# ── Helpers thời gian ─────────────────────────────────────────────────────────

def _now_vn() -> datetime:
    return datetime.now(TZ)


def _today_ddmmyyyy() -> str:
    return _now_vn().strftime("%d/%m/%Y")


def _today_iso() -> str:
    return _now_vn().strftime("%Y-%m-%d")


def _hhmm() -> str:
    return _now_vn().strftime("%H:%M")


# ── Gửi Telegram ──────────────────────────────────────────────────────────────

async def _send(bot, text: str):
    if not text.strip():
        return
    chat_id = get_odo_chat_id()
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.error(f"[ODO Bot] send failed (MD): {e}")
        try:
            # Fallback: gửi plain text
            plain = text.replace("*", "").replace("\\.", ".").replace("\\_", "_")
            await bot.send_message(chat_id=chat_id, text=plain)
        except Exception as e2:
            logger.error(f"[ODO Bot] send plain fallback failed: {e2}")


# ── Đọc Google Sheets ODO ─────────────────────────────────────────────────────

def _read_odo_sheet() -> Dict:
    """
    Trả về { "dd/mm/yyyy": { "Tên Kho": set(biển_số) } }
    """
    import re, unicodedata

    sa_json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    import json as _json

    info = None
    if sa_json_env:
        try:
            info = _json.loads(sa_json_env)
        except Exception:
            if os.path.exists(sa_json_env):
                with open(sa_json_env, encoding="utf-8") as f:
                    info = _json.load(f)

    if not info:
        for cand in ["alien-oarlock-499610-a5-2d813b6cc71d.json", "service_account.json"]:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), cand)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    info = _json.load(f)
                break

    if not info:
        raise RuntimeError("Không tìm thấy Google Service Account JSON")

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build("sheets", "v4", credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=get_odo_sheet_id(),
        range=f"'{get_odo_sheet_name()}'!A:Z",
    ).execute()

    rows = result.get("values", [])
    if not rows or len(rows) < 2:
        return {}

    headers = [str(h).strip() for h in rows[0]]

    # Auto detect cột biển số
    BIEN_SO_ALIASES = ["biển số", "bien so", "bienso", "plate", "biển số xe", "bien so xe"]
    ID_XE_ALIASES   = ["id xe", "idxe", "mã xe"]

    def _find_col(aliases):
        for i, h in enumerate(headers):
            hn = unicodedata.normalize("NFKD", h.lower())
            hn = "".join(c for c in hn if not unicodedata.combining(c))
            for a in aliases:
                an = unicodedata.normalize("NFKD", a.lower())
                an = "".join(c for c in an if not unicodedata.combining(c))
                if an in hn or hn in an:
                    return i
        return -1

    col_date    = 0  # Cột A
    col_kho     = 5  # Cột F
    col_bien_so = _find_col(BIEN_SO_ALIASES)
    col_id_xe   = _find_col(ID_XE_ALIASES)

    logger.info(f"[ODO Sheet] headers={headers[:8]}, col_bien_so={col_bien_so}, col_id_xe={col_id_xe}")

    from datetime import datetime as _dt

    def _parse_date(raw):
        raw = str(raw).strip()
        for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"]:
            try:
                return _dt.strptime(raw[:10], fmt).strftime("%d/%m/%Y")
            except ValueError:
                pass
        try:
            serial = float(raw)
            if 40000 < serial < 60000:
                base = _dt(1899, 12, 30)
                return (base + timedelta(days=serial)).strftime("%d/%m/%Y")
        except ValueError:
            pass
        return None

    result_dict: Dict = {}
    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) <= col_kho:
            continue
        date_str = _parse_date(row[col_date] if col_date < len(row) else "")
        if not date_str:
            continue
        kho = str(row[col_kho]).strip() if col_kho < len(row) else ""
        if not kho:
            continue

        bien_so = str(row[col_bien_so]).strip() if col_bien_so != -1 and col_bien_so < len(row) else ""
        id_xe   = str(row[col_id_xe]).strip()   if col_id_xe   != -1 and col_id_xe   < len(row) else ""

        xe_key = bien_so.upper() if bien_so else (f"ID:{id_xe}" if id_xe else f"ROW:{row_idx}")

        result_dict.setdefault(date_str, {}).setdefault(kho, set()).add(xe_key)

    logger.info(f"[ODO Sheet] Đọc xong: {len(result_dict)} ngày có dữ liệu")
    return result_dict


# ── Đọc fleet + daily từ API nội bộ ──────────────────────────────────────────

def _get_fleet() -> List[Dict]:
    import httpx
    token = os.environ.get("API_SECRET_TOKEN", "")
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                f"{get_dashboard_url()}/api/vehicle-fleet-by-warehouse",
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            return r.json().get("data", [])
    except Exception as e:
        logger.error(f"[ODO] get_fleet error: {e}")
        return []


def _get_daily(date_iso: str) -> List[Dict]:
    import httpx
    token = os.environ.get("API_SECRET_TOKEN", "")
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                f"{get_dashboard_url()}/api/vehicle-daily",
                headers={"Authorization": f"Bearer {token}"},
                params={"date": date_iso},
            )
            r.raise_for_status()
            return r.json().get("data", [])
    except Exception as e:
        logger.error(f"[ODO] get_daily({date_iso}) error: {e}")
        return []


# ── Chuẩn hóa tên kho ─────────────────────────────────────────────────────────

def _ascii_key(name: str) -> str:
    import re, unicodedata
    name = str(name).strip().lower()
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_s = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_s)


def _resolve_kho(raw_name: str, fleet_ascii: Dict[str, str]) -> str:
    key = _ascii_key(raw_name)
    if key in fleet_ascii:
        return fleet_ascii[key]
    # Partial match
    for fk, fn in fleet_ascii.items():
        if key and len(key) >= 6 and (key in fk or fk in key):
            return fn
    return raw_name


# ── Core: tính toán ODO ───────────────────────────────────────────────────────

def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special chars."""
    import re
    return re.sub(r"([_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!])", r"\\\1", str(text))


def _calc_and_report(date_ddmm: str, fleet: List[Dict], daily: List[Dict], odo_data: Dict):
    """
    Tính trạng thái từng kho. Trả về (messages: list[str], all_ok: bool)
    """
    fleet_ascii = {_ascii_key(k["warehouseName"]): k["warehouseName"] for k in fleet}

    # Index daily theo tên chuẩn
    daily_by_kho: Dict = {}
    for d in daily:
        raw = d.get("warehouseName", "") or d.get("ten_kho", "")
        canon = _resolve_kho(raw, fleet_ascii)
        daily_by_kho.setdefault(canon, {"inactive": 0, "additional": 0})
        daily_by_kho[canon]["inactive"]   += int(d.get("inactiveVehicleCount", 0) or 0)
        daily_by_kho[canon]["additional"] += int(d.get("additionalVehicleCount", 0) or 0)

    # Index ODO theo tên chuẩn
    odo_day = odo_data.get(date_ddmm, {})
    odo_by_kho: Dict = {}
    for raw_name, plates in odo_day.items():
        canon = _resolve_kho(raw_name, fleet_ascii)
        odo_by_kho.setdefault(canon, set()).update(plates)

    missing_list = []
    for kho in fleet:
        w_name  = kho["warehouseName"]
        w_id    = kho.get("warehouseId", w_name)
        active  = int(kho.get("activeVehicleCount", 0) or 0)
        d_info  = daily_by_kho.get(w_name, {})
        inactive   = d_info.get("inactive", 0)
        additional = d_info.get("additional", 0)
        expected   = max(active - inactive + additional, 0)
        reported   = len(odo_by_kho.get(w_name, set()))
        missing    = max(expected - reported, 0)

        logger.info(
            f"[ODO Calc] {w_name}: active={active} off={inactive} add={additional} "
            f"exp={expected} rep={reported} miss={missing}"
        )

        # Lưu state
        state_key = f"{_today_iso()}|{w_id}"
        _odo_state[state_key] = {
            "report_date":   _today_iso(),
            "warehouse_id":  w_id,
            "warehouse_name": w_name,
            "expected":  expected,
            "reported":  reported,
            "missing":   missing,
            "status":    "completed" if missing == 0 else "pending",
        }

        if missing > 0:
            missing_list.append({
                "name":       w_name,
                "active":     active,
                "inactive":   inactive,
                "additional": additional,
                "expected":   expected,
                "reported":   reported,
                "missing":    missing,
            })

    _save_state()
    return missing_list


# ── Soạn tin nhắn ─────────────────────────────────────────────────────────────

def _build_missing_msg(date_ddmm: str, check_time: str, missing_list: List[Dict]) -> str:
    lines = [
        "🚨 *BÁO CÁO KHO NHẬP THIẾU ODO*",
        "",
        f"📅 Ngày kiểm tra: {_escape_md(date_ddmm)}",
        f"⏰ Thời gian: {_escape_md(check_time)}",
        "",
    ]
    for idx, m in enumerate(missing_list, 1):
        lines.append(f"{idx}\\. {_escape_md(m['name'])}")
        lines.append(f"   • Xe cố định: {m['active']}")
        if m["inactive"]:
            lines.append(f"   • Xe không hoạt động: {m['inactive']}")
        if m["additional"]:
            lines.append(f"   • Xe tăng cường: {m['additional']}")
        lines.append(f"   • Số xe phải báo ODO: *{m['expected']}*")
        lines.append(f"   • Đã báo ODO: {m['reported']}")
        lines.append(f"   • Còn thiếu: *{m['missing']} xe*")
        lines.append("")

    total_kho = len(missing_list)
    total_xe  = sum(m["missing"] for m in missing_list)
    lines += [
        "📊 *Tổng cộng:*",
        f"   • Số kho còn thiếu ODO: {total_kho} kho",
        f"   • Tổng số xe còn thiếu ODO: {total_xe} xe",
        "",
        "⚠️ Đề nghị các kho kiểm tra và bổ sung ODO đầy đủ\\.",
    ]
    return "\n".join(lines)


def _build_complete_msg(date_ddmm: str) -> str:
    return (
        f"✅ *BÁO CÁO ODO*\n\n"
        f"Tất cả các kho đã nhập đầy đủ ODO trong ngày {_escape_md(date_ddmm)}\\."
    )


def _build_daily_vehicle_msg(date_ddmm: str, daily: List[Dict]) -> str:
    inactive_recs  = [d for d in daily if d.get("loai") == "Xe không hoạt động" or int(d.get("inactiveVehicleCount", 0) or 0) > 0]
    additional_recs = [d for d in daily if d.get("loai") == "Xe tăng cường" or int(d.get("additionalVehicleCount", 0) or 0) > 0]

    lines = ["🚚 *BÁO CÁO XE VẬN HÀNH DAILY*", "", f"📅 Ngày: {_escape_md(date_ddmm)}", ""]

    lines.append("🔴 *Xe không hoạt động:*")
    total_off = 0
    if inactive_recs:
        for i, d in enumerate(inactive_recs, 1):
            name = _escape_md(d.get("warehouseName") or d.get("ten_kho", "?"))
            cnt  = int(d.get("inactiveVehicleCount") or d.get("so_luong_xe", 0) or 0)
            bien = _escape_md(d.get("bien_so_xe", ""))
            detail = f" \\({bien}\\)" if bien else ""
            lines.append(f"{i}\\. {name}: {cnt} xe{detail}")
            total_off += cnt
        lines.append(f"\n📌 Tổng: *{total_off} xe*")
    else:
        lines.append("   • 0 xe")

    lines += ["", "🟢 *Xe tăng cường:*"]
    total_add = 0
    if additional_recs:
        for i, d in enumerate(additional_recs, 1):
            name = _escape_md(d.get("warehouseName") or d.get("ten_kho", "?"))
            cnt  = int(d.get("additionalVehicleCount") or d.get("so_luong_xe", 0) or 0)
            ncc  = _escape_md(d.get("ten_ncc", ""))
            detail = f" \\(NCC: {ncc}\\)" if ncc else ""
            lines.append(f"{i}\\. {name}: {cnt} xe{detail}")
            total_add += cnt
        lines.append(f"\n📌 Tổng: *{total_add} xe*")
    else:
        lines.append("   • 0 xe")

    return "\n".join(lines)


def _build_old_days_msg(pending_records: List[Dict]) -> str:
    if not pending_records:
        return ""
    from collections import defaultdict
    by_kho: Dict = defaultdict(list)
    for p in pending_records:
        by_kho[p["warehouse_name"]].append(p)

    lines = ["🚨 *ODO CÒN THIẾU NHIỀU NGÀY*", ""]
    for kho_name, records in sorted(by_kho.items()):
        records_sorted = sorted(records, key=lambda r: r["report_date"])
        lines.append(f"🏭 *{_escape_md(kho_name)}*")
        total = 0
        for r in records_sorted:
            # Chuyển YYYY-MM-DD → dd/mm/yyyy
            parts = r["report_date"].split("-")
            d_fmt = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else r["report_date"]
            m = r["missing"]
            lines.append(f"   • Ngày {_escape_md(d_fmt)}: thiếu {m} xe")
            total += m
        lines.append(f"   ➡️ Tổng còn thiếu: *{total} lượt xe ODO*")
        lines.append("")
    return "\n".join(lines)


# ── Job functions ─────────────────────────────────────────────────────────────

async def _job_odo_check(bot, check_time: str, date_str: Optional[str] = None):
    """Kiểm tra ODO và gửi báo cáo."""
    if date_str is None:
        date_str = _today_ddmmyyyy()

    date_key = date_str.replace("/", "-")
    idem_key = f"odo_current_{date_key}_{check_time.replace(':', '')}"
    if _check_idem(idem_key):
        logger.info(f"[ODO] Skip duplicate: {idem_key}")
        return

    logger.info(f"[ODO] Check start: date={date_str}, time={check_time}")
    errors = []

    # Chạy blocking IO trong executor
    loop = asyncio.get_event_loop()
    fleet = []
    daily = []
    odo_data = {}

    try:
        fleet = await loop.run_in_executor(None, _get_fleet)
        logger.info(f"[ODO] Fleet: {len(fleet)} kho")
    except Exception as e:
        errors.append(f"Fleet API: {e}")

    if not fleet:
        if errors:
            await _send(bot, f"❌ *BOT ODO* không đọc được Fleet API\\. Kiểm tra dashboard\\.")
        _set_idem(idem_key)
        return

    try:
        date_iso = _today_iso() if date_str == _today_ddmmyyyy() else \
                   "-".join(reversed(date_str.split("/")))
        daily = await loop.run_in_executor(None, _get_daily, date_iso)
        logger.info(f"[ODO] Daily: {len(daily)} records")
    except Exception as e:
        errors.append(f"Daily API: {e}")

    try:
        odo_data = await loop.run_in_executor(None, _read_odo_sheet)
    except Exception as e:
        errors.append(f"Google Sheets: {e}")
        logger.error(f"[ODO] Sheet read error: {e}")
        if errors:
            await _send(bot, f"❌ *BOT ODO* không đọc được Google Sheets ODO\\.")
        _set_idem(idem_key)
        return

    # Tính toán
    missing_list = _calc_and_report(date_str, fleet, daily, odo_data)

    # Gửi báo cáo
    if missing_list:
        msg = _build_missing_msg(date_str, check_time, missing_list)
        await _send(bot, msg)
    else:
        msg = _build_complete_msg(date_str)
        await _send(bot, msg)

    _set_idem(idem_key)
    logger.info(f"[ODO] Check done: {idem_key}, missing_kho={len(missing_list)}")


async def _job_xe_daily(bot):
    """Gửi báo cáo xe vận hành — chỉ 1 lần/ngày lúc 18:00."""
    global _xe_daily_sent
    today = _today_iso()
    idem_key = f"xe_daily_{today}_1800"
    if _check_idem(idem_key):
        _xe_daily_sent = today
        return

    loop = asyncio.get_event_loop()
    try:
        daily = await loop.run_in_executor(None, _get_daily, today)
    except Exception as e:
        await _send(bot, f"❌ BOT ODO không đọc được Xe Daily API\\.")
        return

    msg = _build_daily_vehicle_msg(_today_ddmmyyyy(), daily)
    await _send(bot, msg)
    _set_idem(idem_key)
    _xe_daily_sent = today
    logger.info(f"[ODO] Xe daily sent for {today}")


async def _job_remind_old_days(bot):
    """Nhắc lại các ngày cũ (< today) còn thiếu ODO."""
    today_iso = _today_iso()
    pending = [
        v for v in _odo_state.values()
        if v.get("status") == "pending" and v.get("report_date", "") < today_iso
    ]
    if not pending:
        return

    check_time = _hhmm()
    idem_key = f"odo_old_{today_iso}_{check_time.replace(':', '')}"
    if _check_idem(idem_key):
        return

    logger.info(f"[ODO] Reminder old days: {len(pending)} records")
    msg = _build_old_days_msg(pending)
    if msg:
        await _send(bot, msg)
    _set_idem(idem_key)


# ── Loop chính (asyncio-based scheduler) ─────────────────────────────────────

async def _odo_scheduler_loop(bot):
    """
    Loop chạy mỗi phút, kiểm tra giờ để trigger job đúng mốc.
    Không dùng APScheduler để tránh conflict với event loop của FastAPI.
    """
    logger.info("[ODO Scheduler] Loop started.")

    # Mốc kiểm tra ODO ngày hiện tại (giờ, phút)
    ODO_CHECK_TIMES = [(18, 0), (19, 0), (21, 0), (23, 0)]
    # Mốc nhắc lại ngày cũ (mỗi 2 giờ từ 7:00 đến 23:00)
    REMIND_OLD_TIMES = [(h, 0) for h in range(7, 24, 2)]

    while True:
        now = _now_vn()
        h, m = now.hour, now.minute

        # Trigger khi đúng phút 0 của các mốc
        if m == 0:
            check_time = f"{h:02d}:{m:02d}"

            # 18:00 → gửi xe daily trước
            if (h, m) == (18, 0):
                asyncio.create_task(_job_xe_daily(bot))

            # Kiểm tra ODO ngày hiện tại
            if (h, m) in ODO_CHECK_TIMES:
                asyncio.create_task(_job_odo_check(bot, check_time))

            # Nhắc lại ngày cũ
            if (h, m) in REMIND_OLD_TIMES:
                asyncio.create_task(_job_remind_old_days(bot))

        # Ngủ đến đầu phút tiếp theo (tránh drift)
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        sleep_secs = (next_minute.astimezone(TZ) - _now_vn()).total_seconds()
        await asyncio.sleep(max(sleep_secs, 1))


# ── Public API: gọi từ main.py startup ───────────────────────────────────────

async def run_odo_scheduler():
    """
    Khởi động ODO Bot + Scheduler.
    Gọi qua: asyncio.create_task(run_odo_scheduler())
    """
    token = get_odo_token()
    if not token:
        logger.warning("[ODO Scheduler] ODO_BOT_TOKEN chưa được đặt — scheduler không chạy.")
        print("[ODO Scheduler WARNING] ODO_BOT_TOKEN chưa được cài đặt trong Variables!")
        return

    _load_state()

    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        from telegram import Update

        global _odo_bot_app

        _odo_bot_app = Application.builder().token(token).build()

        # Khởi tạo application
        await _odo_bot_app.initialize()
        await _odo_bot_app.start()
        bot = _odo_bot_app.bot

        # Command handlers trong Telegram
        async def _cmd_odo(update: Update, context):
            text = update.message.text.strip() if update.message else ""
            date_str = None
            if "_" in text and len(text.split("_")[1]) == 8:
                raw = text.split("_")[1]
                date_str = f"{raw[:2]}/{raw[2:4]}/{raw[4:]}"
            await update.message.reply_text(f"⏳ Đang kiểm tra ODO {date_str or 'hôm nay'}...")
            await manual_odo_check(bot, date_str=date_str)

        async def _cmd_xe_daily(update: Update, context):
            await update.message.reply_text("⏳ Đang lấy dữ liệu xe vận hành...")
            await manual_xe_daily(bot)

        async def _cmd_status(update: Update, context):
            pending = [v for v in _odo_state.values() if v.get("status") == "pending"]
            if not pending:
                await update.message.reply_text("✅ Không có ngày nào thiếu ODO.")
            else:
                msg = _build_old_days_msg(pending)
                await _send(bot, msg)

        _odo_bot_app.add_handler(CommandHandler("odo", _cmd_odo))
        _odo_bot_app.add_handler(CommandHandler("xe_daily", _cmd_xe_daily))
        _odo_bot_app.add_handler(CommandHandler("status", _cmd_status))
        _odo_bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/odo_\d{8}"), _cmd_odo))

        # Bắt đầu polling trong background task
        asyncio.create_task(
            _odo_bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        )

        logger.info(f"[ODO Bot] Started with command handlers (/odo, /xe_daily, /status). Chat ID: {ODO_CHAT_ID}")

        # Bắt đầu scheduler loop
        await _odo_scheduler_loop(bot)

    except Exception as e:
        logger.error(f"[ODO Scheduler] Fatal error: {e}", exc_info=True)


# ── Command handlers (dùng từ odo_bot_handler.py) ────────────────────────────

async def manual_odo_check(bot, date_str: Optional[str] = None):
    """Chạy kiểm tra ODO thủ công — dùng cho lệnh /odo."""
    check_time = _hhmm()
    await _job_odo_check(bot, check_time, date_str)


async def manual_xe_daily(bot):
    """Gửi báo cáo xe daily thủ công — dùng cho lệnh /xe_daily."""
    await _job_xe_daily(bot)
