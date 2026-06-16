"""
giao_hang_scheduler.py
=======================
Scheduler tu dong gui bao cao "don can giao hom nay" qua Telegram.
Chay cung FastAPI app nhu background task.

Lich: 09:30 va 13:30 hang ngay (Asia/Ho_Chi_Minh)
- 09:30: Bao cao binh thuong + luu danh sach Order code lam moc
- 13:30: Bao cao binh thuong + so sanh don moi voi 09:30
"""

import os, csv, io, json, asyncio, logging
from datetime import datetime, date
from zoneinfo import ZoneInfo
import httpx

log = logging.getLogger(__name__)

# =========================================================
# CAU HINH
# =========================================================
TELEGRAM_BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GIAO_HANG_CHAT_ID     = os.environ.get("GIAO_HANG_CHAT_ID", "")

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
COL_PRIORITY = 0  # A
COL_KHO      = 2  # C
COL_PIC      = 3  # D
COL_ORDER    = 4  # E
COL_ACTION   = 5  # F
COL_KHACH    = 6  # G
COL_DIACHI   = 7  # H
COL_NGAY     = 8  # I
COL_LUUKHO   = 9  # J

SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# =========================================================
# TRANG THAI NOI BO
# =========================================================
# Luu du lieu bao cao 09:30 de so sanh voi 13:30
# Format: { date: {"orders": list[dict], "order_codes": set[str]} }
_morning_snapshot: dict = {}

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
    log.info(f"[GiaoHang] Doc CSV: Sheet={SOURCE_SPREADSHEET_ID} GID={SOURCE_GID}")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise RuntimeError(f"Khong doc duoc CSV: HTTP {resp.status_code}")

    content = resp.content.decode("utf-8-sig")
    reader  = csv.reader(io.StringIO(content))
    rows    = list(reader)

    if len(rows) < 4:
        raise RuntimeError(f"CSV qua it dong: {len(rows)}")

    header = rows[2]  # Dong 3 = header

    def get(row, idx):
        return row[idx].strip() if idx < len(row) else ""

    data = []
    for r in rows[3:]:  # Dong 4+ = data
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
# SO SANH DON MOI (13:30 vs 09:30)
# =========================================================
def find_new_orders(current_filtered: list[dict], today: date) -> dict:
    """
    So sanh don hien tai voi snapshot 09:30.
    Tra ve:
    {
        "has_morning_data": bool,
        "new_orders": list[dict],          # Cac don moi
        "by_kho": {kho: {khach: [orders]}} # Nhom theo kho + khach
    }
    """
    snapshot = _morning_snapshot.get(today)

    if snapshot is None:
        return {
            "has_morning_data": False,
            "new_orders": [],
            "by_kho": {}
        }

    morning_codes = snapshot["order_codes"]
    new_orders = [
        r for r in current_filtered
        if r["order"] and r["order"] not in morning_codes
    ]

    # Nhom theo kho -> khach -> list orders
    by_kho: dict = {}
    for r in new_orders:
        kho   = r["kho"] or "(Chưa xác định)"
        khach = r["khach"] or "(Chưa xác định)"
        if kho not in by_kho:
            by_kho[kho] = {}
        if khach not in by_kho[kho]:
            by_kho[kho][khach] = []
        by_kho[kho][khach].append(r)

    log.info(f"[GiaoHang] Don moi (13:30 vs 09:30): {len(new_orders)}")
    return {
        "has_morning_data": True,
        "new_orders": new_orders,
        "by_kho": by_kho
    }


def save_morning_snapshot(filtered: list[dict], today: date):
    """Luu snapshot 09:30 vao bo nho."""
    order_codes = {r["order"] for r in filtered if r["order"]}
    _morning_snapshot[today] = {
        "orders": filtered,
        "order_codes": order_codes,
    }
    log.info(f"[GiaoHang] Da luu snapshot 09:30: {len(order_codes)} order codes")

    # Xoa snapshot cu (giu toi da 2 ngay)
    old_days = [d for d in list(_morning_snapshot.keys()) if d < today]
    for d in old_days:
        del _morning_snapshot[d]


# =========================================================
# TAO GOOGLE SHEET BAO CAO
# =========================================================
def _build_sheet_tabs(filtered: list[dict], kho_summary: dict,
                      comparison: dict, is_afternoon: bool) -> list[dict]:
    """Tao danh sach tabs cho spreadsheet."""
    sheets_def = [
        {"properties": {"title": "Tổng hợp theo kho", "index": 0}},
        {"properties": {"title": "Chi tiết đơn",      "index": 1}},
    ]
    if is_afternoon:
        sheets_def.append({"properties": {"title": "Đơn mới so với 09h30", "index": 2}})
    return sheets_def


def _create_report_sheet_sync(filtered: list[dict], kho_summary: dict,
                              comparison: dict, now: datetime,
                              is_afternoon: bool) -> str:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    info  = json.loads(SA_JSON)
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    time_label = "13h30" if is_afternoon else "09h30"
    title = (
        f"Báo cáo đơn cần giao {time_label} "
        f"- {PIC_FILTER} "
        f"- {now.strftime('%d/%m/%Y')}"
    )
    body = {
        "properties": {"title": title, "locale": "vi_VN"},
        "sheets": _build_sheet_tabs(filtered, kho_summary, comparison, is_afternoon),
    }
    ss    = svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    ss_id = ss["spreadsheetId"]

    # Tab 1: Tong hop theo kho
    tab1  = [["Kho hiện tại", "Số đơn cần giao hôm nay"]]
    tab1 += [[k, v] for k, v in kho_summary.items()]
    tab1 += [["TỔNG CỘNG", len(filtered)]]

    # Tab 2: Chi tiet don
    tab2_h = ["Mức độ ưu tiên", "Kho hiện tại", "PIC", "Order code",
              "Cần làm gì", "Khách", "Địa chỉ giao", "Ngày nhập kho", "Đã lưu kho"]
    tab2   = [tab2_h] + [
        [r["priority"], r["kho"], r["pic"], r["order"],
         r["action"], r["khach"], r["diachi"], r["ngay"], r["luukho"]]
        for r in filtered
    ]

    batch_data = [
        {"range": "'Tổng hợp theo kho'!A1", "values": tab1},
        {"range": "'Chi tiết đơn'!A1",       "values": tab2},
    ]

    # Tab 3 (chi 13:30): Don moi so voi 09h30
    if is_afternoon:
        new_orders = comparison.get("new_orders", [])
        tab3_h = ["Kho hiện tại", "Khách", "Order code", "Cần làm gì",
                  "Mức độ ưu tiên", "Ngày nhập kho", "Đã lưu kho"]
        tab3   = [tab3_h] + [
            [r["kho"], r["khach"], r["order"], r["action"],
             r["priority"], r["ngay"], r["luukho"]]
            for r in new_orders
        ] if new_orders else [tab3_h, ["(Không có đơn mới)"]]
        batch_data.append(
            {"range": "'Đơn mới so với 09h30'!A1", "values": tab3}
        )

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=ss_id,
        body={"valueInputOption": "USER_ENTERED", "data": batch_data},
    ).execute()

    log.info(f"[GiaoHang] Sheet tao OK: {ss_id}")
    return f"https://docs.google.com/spreadsheets/d/{ss_id}/edit"


async def create_report_sheet(filtered, kho_summary, comparison,
                              now, is_afternoon) -> str:
    if not SA_JSON:
        return ""
    try:
        return await asyncio.to_thread(
            _create_report_sheet_sync,
            filtered, kho_summary, comparison, now, is_afternoon
        )
    except Exception as e:
        log.error(f"[GiaoHang] Tao sheet that bai: {e}")
        return ""


# =========================================================
# BUILD TIN NHAN TELEGRAM
# =========================================================
def _build_comparison_section(comparison: dict) -> str:
    """Tao phan so sanh don moi cho tin nhan 13:30."""
    if not comparison.get("has_morning_data"):
        return "\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b> Không có dữ liệu 09:30 để so sánh."

    new_orders = comparison.get("new_orders", [])
    by_kho     = comparison.get("by_kho", {})

    if not new_orders:
        return "\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b> Không phát sinh đơn mới."

    lines = ["\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b>"]
    for kho, khach_map in sorted(by_kho.items()):
        total_kho = sum(len(v) for v in khach_map.values())
        lines.append(f"• Kho <b>{kho}</b>: có thêm <b>{total_kho}</b> đơn mới đến hạn giao.")
        for khach, orders in sorted(khach_map.items(), key=lambda x: -len(x[1])):
            lines.append(f"   - Khách {khach}: {len(orders)} đơn")

    return "\n".join(lines)


def build_message(filtered, kho_summary, sheet_url, now,
                  comparison=None, is_afternoon=False) -> str:
    time_str   = now.strftime("%d/%m/%Y %H:%M")
    label      = "13:30" if is_afternoon else "09:30"

    if not filtered:
        msg = (
            f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY ({label})</b>\n"
            f"PIC: {PIC_FILTER}\n"
            f"Thời gian: {time_str}\n\n"
            f"Hiện không có đơn cần giao trong hôm nay theo điều kiện lọc."
        )
        if is_afternoon and comparison:
            msg += _build_comparison_section(comparison)
        return msg

    kho_lines = "\n".join(
        f"{i}. {kho}: <b>{cnt}</b> đơn"
        for i, (kho, cnt) in enumerate(kho_summary.items(), 1)
    )
    link_part = f"\n\n📄 <b>Link chi tiết:</b>\n{sheet_url}" if sheet_url else ""

    msg = (
        f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY ({label})</b>\n"
        f"PIC: {PIC_FILTER}\n"
        f"Thời gian: {time_str}\n\n"
        f"Tổng đơn cần giao: <b>{len(filtered)}</b> đơn\n\n"
        f"📍 <b>Theo kho:</b>\n{kho_lines}"
        f"{link_part}"
    )

    # Them phan so sanh neu la bao cao 13:30
    if is_afternoon and comparison:
        msg += _build_comparison_section(comparison)

    msg += (
        "\n\n<i>Yêu cầu: Các kho kiểm tra danh sách đơn, ưu tiên xử lý "
        "trong ngày và phản hồi nếu có đơn không giao được.</i>"
    )
    return msg


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
                "chat_id":                chat_id,
                "text":                   text,
                "parse_mode":             "HTML",
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


# =========================================================
# LOGIC CHINH
# =========================================================
async def run_giao_hang_report(label: str = "manual"):
    global _sent_today
    now          = datetime.now(TZ)
    today        = now.date()
    is_afternoon = (label == "13:30")

    if _sent_today.get(label) == today:
        log.info(f"[GiaoHang] Da gui [{label}] hom nay, bo qua.")
        return

    log.info(f"[GiaoHang] === BAT DAU [{label}] {now.strftime('%d/%m/%Y %H:%M')} ===")

    try:
        rows     = await read_source_csv()
        filtered = filter_rows(rows)
        kho_sum  = summarize_by_kho(filtered) if filtered else {}

        # So sanh don moi (chi 13:30)
        comparison = None
        if is_afternoon:
            comparison = find_new_orders(filtered, today)

        # Tao Google Sheet bao cao
        sheet_url = ""
        if filtered:
            sheet_url = await create_report_sheet(
                filtered, kho_sum, comparison or {}, now, is_afternoon
            )

        # Build va gui Telegram
        msg = build_message(
            filtered, kho_sum, sheet_url, now,
            comparison=comparison, is_afternoon=is_afternoon
        )
        ok = await send_telegram(msg)

        if ok:
            _sent_today[label] = today
            log.info(f"[GiaoHang] XONG [{label}]")

            # Luu snapshot sau khi gui thanh cong luc 09:30
            if label == "09:30":
                save_morning_snapshot(filtered, today)
        else:
            log.error(f"[GiaoHang] Gui Telegram that bai [{label}]")

    except Exception as e:
        log.exception(f"[GiaoHang] Loi: {e}")
        try:
            await send_telegram(
                f"❌ <b>Bot GHN Giao Hàng gặp lỗi [{label}]</b>\n"
                f"Thời gian: {now.strftime('%d/%m/%Y %H:%M')}\n"
                f"Lỗi: <code>{str(e)[:300]}</code>"
            )
        except Exception:
            pass


# =========================================================
# BACKGROUND LOOP
# =========================================================
async def run_giao_hang_scheduler():
    """Background task khoi dong cung FastAPI. Wake up moi phut."""
    log.info(f"[GiaoHang] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    log.info(f"[GiaoHang] Sheet: {SOURCE_SPREADSHEET_ID} / GID={SOURCE_GID}")
    log.info(f"[GiaoHang] PIC: '{PIC_FILTER}'")
    log.info(f"[GiaoHang] Chat: {_get_chat_id() or '(chua cau hinh)'}")
    log.info(f"[GiaoHang] Sheets API: {'CO' if SA_JSON else 'KHONG'}")

    # (gio, phut, label)
    SCHEDULE = [(9, 30, "09:30"), (13, 30, "13:30")]

    while True:
        try:
            now = datetime.now(TZ)
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    await run_giao_hang_report(label)
        except Exception as e:
            log.error(f"[GiaoHang] Loi scheduler loop: {e}")
        await asyncio.sleep(60)
