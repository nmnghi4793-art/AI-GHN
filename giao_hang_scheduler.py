"""
giao_hang_scheduler.py
=======================
Scheduler tu dong gui bao cao "don can giao hom nay" qua Telegram.
Chay cung FastAPI app nhu background task.

Lich: 09:30 va 13:30 hang ngay (Asia/Ho_Chi_Minh)

Doc du lieu tu Google Sheet public bang CSV export (khong can API key).
Tuy chon: Tao Google Sheet bao cao moi neu co GOOGLE_SERVICE_ACCOUNT_JSON.
"""

import os, csv, io, json, asyncio, logging
from datetime import datetime, date
from zoneinfo import ZoneInfo
import httpx

log = logging.getLogger(__name__)

# =========================================================
# CAU HINH — lay tu environment variables
# =========================================================
TELEGRAM_BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GIAO_HANG_CHAT_ID     = os.environ.get("GIAO_HANG_CHAT_ID", "")   # Chat ID rieng cho bao cao giao hang
# Neu khong co GIAO_HANG_CHAT_ID, dung WARN_CHAT_ID hoac TELEGRAM_CHAT_ID
def _get_chat_id():
    return (GIAO_HANG_CHAT_ID
            or os.environ.get("WARN_CHAT_ID", "")
            or os.environ.get("TELEGRAM_CHAT_ID", ""))

SOURCE_SPREADSHEET_ID = os.environ.get(
    "GIAO_HANG_SHEET_ID",
    "1AxoVdTpPcYn49qqWzmlYzWsKWk8v9UahErtBntBqn6g"
)
SOURCE_GID     = os.environ.get("GIAO_HANG_SHEET_GID", "566926461")
TIMEZONE_STR   = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ             = ZoneInfo(TIMEZONE_STR)

PIC_FILTER      = os.environ.get("GIAO_HANG_PIC", "Nguyễn Minh Nghị")
ACTION_FILTER   = "giao"
PRIORITY_FILTER = "1: trong hôm nay"

# Cot (0-indexed): A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9
COL_PRIORITY = 0   # A
COL_KHO      = 2   # C
COL_PIC      = 3   # D
COL_ORDER    = 4   # E
COL_ACTION   = 5   # F
COL_KHACH    = 6   # G
COL_DIACHI   = 7   # H
COL_NGAY     = 8   # I
COL_LUUKHO   = 9   # J

SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Tranh gui trung trong cung 1 moc gio
_sent_today: dict = {}


# =========================================================
# DOC DU LIEU QUA CSV EXPORT (khong can API key)
# =========================================================
async def read_source_csv() -> list[dict]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SOURCE_SPREADSHEET_ID}"
        f"/export?format=csv&gid={SOURCE_GID}"
    )
    log.info(f"[GiaoHang] Doc CSV tu Sheet ID={SOURCE_SPREADSHEET_ID} GID={SOURCE_GID}")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise RuntimeError(f"Khong doc duoc CSV: HTTP {resp.status_code}")

    content = resp.content.decode("utf-8-sig")
    reader  = csv.reader(io.StringIO(content))
    rows    = list(reader)

    if len(rows) < 4:
        raise RuntimeError(f"CSV qua it dong: {len(rows)} dong")

    # Dong 3 = header (index 2), dong 4+ = data (index 3+)
    header = rows[2]
    log.info(f"[GiaoHang] Header: {header[:6]}")

    def get(row, idx):
        return row[idx].strip() if idx < len(row) else ""

    data = []
    for r in rows[3:]:
        if not any(r):
            continue
        data.append({
            "priority": get(r, COL_PRIORITY),
            "kho":      get(r, COL_KHO),
            "pic":      get(r, COL_PIC),
            "order":    get(r, COL_ORDER),
            "action":   get(r, COL_ACTION),
            "khach":    get(r, COL_KHACH),
            "diachi":   get(r, COL_DIACHI),
            "ngay":     get(r, COL_NGAY),
            "luukho":   get(r, COL_LUUKHO),
        })

    log.info(f"[GiaoHang] Doc duoc {len(data)} dong")
    return data


# =========================================================
# LOC DU LIEU
# =========================================================
def filter_rows(rows: list[dict]) -> list[dict]:
    out = [
        r for r in rows
        if PIC_FILTER.lower() in r["pic"].lower()
        and r["action"].strip().lower() == ACTION_FILTER.lower()
        and PRIORITY_FILTER.lower() in r["priority"].lower()
    ]
    log.info(f"[GiaoHang] Loc: {len(out)} don thoa dieu kien")
    return out


def summarize_by_kho(filtered: list[dict]) -> dict:
    kho_count: dict = {}
    for r in filtered:
        k = r["kho"] or "(Chưa xác định)"
        kho_count[k] = kho_count.get(k, 0) + 1
    return dict(sorted(kho_count.items(), key=lambda x: -x[1]))


# =========================================================
# TAO GOOGLE SHEET BAO CAO (tuy chon - chi can Sheets API)
# =========================================================
def _create_report_sheet_sync(filtered: list[dict], kho_summary: dict,
                              now: datetime) -> str:
    """Dong bo — duoc goi bang asyncio.to_thread"""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    info  = json.loads(SA_JSON)
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    title = (
        f"Báo cáo đơn cần giao - {PIC_FILTER} "
        f"- {now.strftime('%d/%m/%Y %H:%M')}"
    )
    body = {
        "properties": {"title": title, "locale": "vi_VN"},
        "sheets": [
            {"properties": {"title": "Tổng hợp theo kho", "index": 0}},
            {"properties": {"title": "Chi tiết đơn",      "index": 1}},
        ],
    }
    ss    = svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    ss_id = ss["spreadsheetId"]

    tab1  = [["Kho hiện tại", "Số đơn cần giao hôm nay"]]
    tab1 += [[k, v] for k, v in kho_summary.items()]
    tab1 += [["TỔNG CỘNG", len(filtered)]]

    tab2_h = ["Mức độ ưu tiên", "Kho hiện tại", "PIC", "Order code",
              "Cần làm gì", "Khách", "Địa chỉ giao", "Ngày nhập kho", "Đã lưu kho"]
    tab2   = [tab2_h] + [
        [r["priority"], r["kho"], r["pic"], r["order"],
         r["action"], r["khach"], r["diachi"], r["ngay"], r["luukho"]]
        for r in filtered
    ]

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=ss_id,
        body={"valueInputOption": "USER_ENTERED", "data": [
            {"range": "'Tổng hợp theo kho'!A1", "values": tab1},
            {"range": "'Chi tiết đơn'!A1",       "values": tab2},
        ]},
    ).execute()

    log.info(f"[GiaoHang] Tao sheet OK: {ss_id}")
    return f"https://docs.google.com/spreadsheets/d/{ss_id}/edit"


async def create_report_sheet(filtered, kho_summary, now) -> str:
    if not SA_JSON:
        log.info("[GiaoHang] Khong co SA_JSON, bo qua tao sheet.")
        return ""
    try:
        return await asyncio.to_thread(
            _create_report_sheet_sync, filtered, kho_summary, now
        )
    except Exception as e:
        log.error(f"[GiaoHang] Tao sheet that bai: {e}")
        return ""


# =========================================================
# GUI TELEGRAM
# =========================================================
async def send_telegram(text: str) -> bool:
    chat_id = _get_chat_id()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        log.error("[GiaoHang] Thieu TELEGRAM_BOT_TOKEN hoac chat ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json={
                "chat_id":   chat_id,
                "text":      text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            })
        if r.status_code == 200:
            log.info("[GiaoHang] Gui Telegram OK")
            return True
        log.error(f"[GiaoHang] Telegram loi {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        log.error(f"[GiaoHang] Telegram exception: {e}")
        return False


def build_message(filtered, kho_summary, sheet_url, now) -> str:
    time_str = now.strftime("%d/%m/%Y %H:%M")

    if not filtered:
        return (
            f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY</b>\n"
            f"PIC: {PIC_FILTER}\n"
            f"Thời gian: {time_str}\n\n"
            f"Hiện không có đơn cần giao trong hôm nay theo điều kiện lọc."
        )

    kho_lines = "\n".join(
        f"{i}. {kho}: <b>{cnt}</b> đơn"
        for i, (kho, cnt) in enumerate(kho_summary.items(), 1)
    )

    link_part = f"\n\n📄 <b>Link chi tiết:</b>\n{sheet_url}" if sheet_url else ""

    return (
        f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY</b>\n"
        f"PIC: {PIC_FILTER}\n"
        f"Thời gian: {time_str}\n\n"
        f"Tổng đơn cần giao: <b>{len(filtered)}</b> đơn\n\n"
        f"📍 <b>Theo kho:</b>\n{kho_lines}"
        f"{link_part}\n\n"
        f"<i>Yêu cầu: Các kho kiểm tra danh sách đơn, ưu tiên xử lý trong ngày "
        f"và phản hồi nếu có đơn không giao được.</i>"
    )


# =========================================================
# LOGIC CHINH — CHAY 1 LAN
# =========================================================
async def run_giao_hang_report(label: str = "manual"):
    global _sent_today
    now   = datetime.now(TZ)
    today = now.date()

    if _sent_today.get(label) == today:
        log.info(f"[GiaoHang] Da gui [{label}] hom nay, bo qua.")
        return

    log.info(f"[GiaoHang] === BAT DAU BAO CAO [{label}] {now.strftime('%d/%m/%Y %H:%M')} ===")

    try:
        rows     = await read_source_csv()
        filtered = filter_rows(rows)
        kho_sum  = summarize_by_kho(filtered) if filtered else {}

        sheet_url = ""
        if filtered:
            sheet_url = await create_report_sheet(filtered, kho_sum, now)

        msg = build_message(filtered, kho_sum, sheet_url, now)
        ok  = await send_telegram(msg)

        if ok:
            _sent_today[label] = today
            log.info(f"[GiaoHang] XONG [{label}]")
        else:
            log.error(f"[GiaoHang] Gui Telegram that bai [{label}]")

    except Exception as e:
        log.exception(f"[GiaoHang] Loi: {e}")
        try:
            await send_telegram(
                f"❌ <b>Bot GHN Giao Hàng gặp lỗi</b>\n"
                f"Thời gian: {now.strftime('%d/%m/%Y %H:%M')}\n"
                f"Lỗi: <code>{str(e)[:300]}</code>"
            )
        except Exception:
            pass


# =========================================================
# BACKGROUND LOOP — chay song song voi FastAPI
# =========================================================
async def run_giao_hang_scheduler():
    """
    Background task chay trong FastAPI startup.
    Wake up moi phut, kiem tra gio gui.
    """
    log.info(f"[GiaoHang] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    log.info(f"[GiaoHang] Sheet ID: {SOURCE_SPREADSHEET_ID} / GID: {SOURCE_GID}")
    log.info(f"[GiaoHang] PIC filter: '{PIC_FILTER}'")
    log.info(f"[GiaoHang] Chat ID: {_get_chat_id() or '(chua cau hinh)'}")
    log.info(f"[GiaoHang] Sheets API: {'CO' if SA_JSON else 'KHONG (chi gui Telegram)'}")

    # Lich gui: (gio, phut, label)
    SCHEDULE = [(9, 30, "09:30"), (13, 30, "13:30")]

    while True:
        try:
            now = datetime.now(TZ)
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    await run_giao_hang_report(label)
        except Exception as e:
            log.error(f"[GiaoHang] Loi scheduler loop: {e}")
        await asyncio.sleep(60)  # Kiem tra moi 1 phut
