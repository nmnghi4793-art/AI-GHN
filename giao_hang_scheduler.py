"""
giao_hang_scheduler.py
=======================
Scheduler tu dong gui bao cao "don can giao hom nay" qua Telegram.
Chay cung FastAPI app nhu background task.

Lich: 09:30, 13:30 va 17:30 hang ngay (Asia/Ho_Chi_Minh)
- 09:30 : Ghi tab 9h30 + Don_han_ngay_mai_ngay_mot + gui Telegram (kem du kien ngay mai/ngay mot) + pin
- 13:30 : Ghi tab 13h30 + Don_han_ngay_mai_ngay_mot + so sanh vs 9h30 + gui Telegram + pin
- 17:30 : Ghi tab 17h30 + so sanh vs 13h30 + gui Telegram + pin

Sheet bao cao co dinh:
  REPORT_SHEET_ID = 1wpWMZRAaoaQXdmTL7dcKJ5PUFrmd8vESQmHj2ysNTHc
  (Phai share cho service account lam Editor truoc)

4 tab trong sheet bao cao:
  - "9h30"                     (du lieu moc 09:30, ghi de moi ngay)
  - "13h30"                    (du lieu moc 13:30, ghi de moi ngay)
  - "17h30"                    (du lieu moc 17:30, ghi de moi ngay)
  - "Don_han_ngay_mai_ngay_mot" (don uu tien 2+3, cap nhat luc 09:30 va 13:30)
"""

import os, csv, io, json, asyncio, logging
from datetime import datetime, date
from zoneinfo import ZoneInfo
import httpx

log = logging.getLogger(__name__)

# =========================================================
# CAU HINH
# =========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GIAO_HANG_CHAT_ID  = os.environ.get("GIAO_HANG_CHAT_ID", "")

def _get_chat_id():
    return (GIAO_HANG_CHAT_ID
            or os.environ.get("WARN_CHAT_ID", "")
            or os.environ.get("TELEGRAM_CHAT_ID", ""))

# Sheet nguon (chi doc - public CSV export, khong can auth)
SOURCE_SPREADSHEET_ID = os.environ.get(
    "GIAO_HANG_SHEET_ID",
    "1AxoVdTpPcYn49qqWzmlYzWsKWk8v9UahErtBntBqn6g"
)
SOURCE_GID = os.environ.get("GIAO_HANG_SHEET_GID", "566926461")

# Sheet bao cao co dinh (can share service account lam Editor)
REPORT_SHEET_ID  = os.environ.get(
    "REPORT_SHEET_ID",
    "1wpWMZRAaoaQXdmTL7dcKJ5PUFrmd8vESQmHj2ysNTHc"
)
REPORT_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{REPORT_SHEET_ID}/edit"

TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TIMEZONE_STR)
except Exception:
    from datetime import timezone, timedelta
    TZ = timezone(timedelta(hours=7))

PIC_FILTER      = os.environ.get("GIAO_HANG_PIC", "Nguyễn Minh Nghị")
ACTION_FILTER   = "giao"
PRIORITY_TODAY  = "1: trong hôm nay"
PRIORITY_NEXT   = ["2: trong ngày mai", "3: trong ngày mốt"]

# Cot (0-indexed): A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9
COL_PRIORITY = 0  # A: Muc do uu tien
COL_KHO      = 2  # C: Kho hien tai
COL_PIC      = 3  # D: PIC
COL_ORDER    = 4  # E: Order code
COL_ACTION   = 5  # F: Can lam gi
COL_KHACH    = 6  # G: Khach
COL_DIACHI   = 7  # H: Dia chi giao
COL_NGAY     = 8  # I: Ngay nhap kho
COL_LUUKHO   = 9  # J: Da luu kho

SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# Ten 4 tab trong sheet bao cao
TAB_9H30    = "9h30"
TAB_13H30   = "13h30"
TAB_17H30   = "17h30"
TAB_NEXT    = "Don_han_ngay_mai_ngay_mot"

# Map label -> ten tab
LABEL_TO_TAB = {
    "09:30": TAB_9H30,
    "13:30": TAB_13H30,
    "17:30": TAB_17H30,
}

# Map so sanh: tab hien tai so voi tab truoc
COMPARE_TAB = {
    "13:30": TAB_9H30,
    "17:30": TAB_13H30,
}

COMPARE_LABEL = {
    "13:30": "09:30",
    "17:30": "13:30",
}

# =========================================================
# TRANG THAI NOI BO
# =========================================================
# Tranh gui trung: {label: date}
_sent_today: dict = {}


# =========================================================
# DOC DU LIEU QUA CSV EXPORT (khong can API key)
# =========================================================
async def read_source_csv() -> list[dict]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SOURCE_SPREADSHEET_ID}"
        f"/export?format=csv&gid={SOURCE_GID}"
    )
    log.info(f"[GiaoHang] Doc CSV: GID={SOURCE_GID}")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise RuntimeError(f"Khong doc duoc CSV: HTTP {resp.status_code}")

    content = resp.content.decode("utf-8-sig")
    rows    = list(csv.reader(io.StringIO(content)))

    if len(rows) < 4:
        raise RuntimeError(f"CSV qua it dong: {len(rows)}")

    def get(row, idx):
        return row[idx].strip() if idx < len(row) else ""

    data = []
    for r in rows[3:]:  # Dong 4+ la du lieu
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
def _base_filter(rows: list[dict]) -> list[dict]:
    """Loc chung: PIC va can lam gi = giao."""
    return [
        r for r in rows
        if PIC_FILTER.lower() in r["pic"].lower()
        and r["action"].strip().lower() == ACTION_FILTER.lower()
    ]


def filter_rows_today(rows: list[dict]) -> list[dict]:
    """Loc: priority = '1: trong hom nay'."""
    base = _base_filter(rows)
    out  = [r for r in base if PRIORITY_TODAY.lower() in r["priority"].lower()]
    log.info(f"[GiaoHang] Loc hom nay (p=1): {len(out)} don")
    return out


def filter_rows_next_days(rows: list[dict]) -> list[dict]:
    """Loc: priority = 2 hoac 3 (ngay mai / ngay mot)."""
    base = _base_filter(rows)
    out  = [
        r for r in base
        if any(p.lower() in r["priority"].lower() for p in PRIORITY_NEXT)
    ]
    log.info(f"[GiaoHang] Loc ngay mai/ngay mot (p=2,3): {len(out)} don")
    return out


def summarize_by_kho(filtered: list[dict]) -> dict:
    kho_count: dict = {}
    for r in filtered:
        k = r["kho"] or "(Chưa xác định)"
        kho_count[k] = kho_count.get(k, 0) + 1
    return dict(sorted(kho_count.items(), key=lambda x: -x[1]))


# =========================================================
# DOC ORDER CODES TU TAB SHEET BAO CAO (de so sanh)
# =========================================================
def _read_tab_order_codes_sync(svc, ss_id: str, tab_name: str) -> set[str]:
    """Lay tat ca order codes tu mot tab trong sheet bao cao."""
    try:
        result = svc.spreadsheets().values().get(
            spreadsheetId=ss_id,
            range=f"'{tab_name}'!A1:Z10000",
        ).execute()
        values = result.get("values", [])
        # Tim header row chua "Order code"
        header_idx = None
        order_col  = None
        for i, row in enumerate(values):
            for j, cell in enumerate(row):
                if "order code" in str(cell).lower():
                    header_idx = i
                    order_col  = j
                    break
            if header_idx is not None:
                break

        if order_col is None:
            log.warning(f"[GiaoHang] Khong tim thay cot 'Order code' trong tab '{tab_name}'")
            return set()

        codes = set()
        for row in values[header_idx + 1:]:
            if order_col < len(row) and row[order_col].strip():
                codes.add(row[order_col].strip())
        log.info(f"[GiaoHang] Doc tab '{tab_name}': {len(codes)} order codes")
        return codes
    except Exception as e:
        log.warning(f"[GiaoHang] Khong doc duoc tab '{tab_name}': {e}")
        return set()


# =========================================================
# SO SANH DON MOI
# =========================================================
def find_new_orders_from_codes(
    current_filtered: list[dict],
    prev_codes: set[str],
    has_prev_data: bool
) -> dict:
    if not has_prev_data:
        return {"has_prev_data": False, "new_orders": [], "by_kho": {}}

    new_orders = [
        r for r in current_filtered
        if r["order"] and r["order"] not in prev_codes
    ]

    by_kho: dict = {}
    for r in new_orders:
        kho   = r["kho"] or "(Chưa xác định)"
        khach = r["khach"] or "(Chưa xác định)"
        by_kho.setdefault(kho, {}).setdefault(khach, []).append(r)

    log.info(f"[GiaoHang] Don moi: {len(new_orders)}")
    return {"has_prev_data": True, "new_orders": new_orders, "by_kho": by_kho}


# =========================================================
# GHI DE SHEET BAO CAO CO DINH (chi can Sheets API)
# =========================================================
def _ensure_tabs_exist(svc, ss_id: str, needed_tabs: list[str]):
    """Tao tab neu chua ton tai trong sheet."""
    meta       = svc.spreadsheets().get(spreadsheetId=ss_id).execute()
    existing   = {s["properties"]["title"] for s in meta.get("sheets", [])}
    to_create  = [t for t in needed_tabs if t not in existing]

    if to_create:
        requests = [
            {"addSheet": {"properties": {"title": t}}}
            for t in to_create
        ]
        svc.spreadsheets().batchUpdate(
            spreadsheetId=ss_id,
            body={"requests": requests}
        ).execute()
        log.info(f"[GiaoHang] Tao tab moi: {to_create}")


def _clear_and_write(svc, ss_id: str, tab: str, values: list[list]):
    """Xoa sach tab roi ghi du lieu moi."""
    svc.spreadsheets().values().clear(
        spreadsheetId=ss_id,
        range=f"'{tab}'!A1:Z10000",
    ).execute()

    if values:
        svc.spreadsheets().values().update(
            spreadsheetId=ss_id,
            range=f"'{tab}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    log.info(f"[GiaoHang] Ghi tab '{tab}': {len(values)} dong")


def _build_detail_rows(filtered: list[dict]) -> list[list]:
    """Tao danh sach row chi tiet don (khong co header)."""
    return [
        [r["priority"], r["kho"], r["pic"], r["order"],
         r["action"], r["khach"], r["diachi"], r["ngay"], r["luukho"]]
        for r in filtered
    ]


DETAIL_COLS = ["Mức độ ưu tiên", "Kho hiện tại", "PIC", "Order code",
               "Cần làm gì", "Khách", "Địa chỉ giao", "Ngày nhập kho", "Đã lưu kho"]


def _write_report_sync(
    label: str,
    filtered_today: list[dict],
    filtered_next: list[dict] | None,
    comparison: dict | None,
    now: datetime,
):
    """Dong bo — chay trong thread rieng."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    info  = json.loads(SA_JSON)
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    # Xac dinh cac tab can ton tai
    all_tabs = [TAB_9H30, TAB_13H30, TAB_17H30, TAB_NEXT]
    _ensure_tabs_exist(svc, REPORT_SHEET_ID, all_tabs)

    time_str = now.strftime("%d/%m/%Y %H:%M")
    tab_name = LABEL_TO_TAB[label]

    # --- Doc order codes tu tab truoc (de so sanh) ---
    prev_codes: set[str] = set()
    has_prev_data = False
    if label in COMPARE_TAB:
        prev_tab = COMPARE_TAB[label]
        prev_codes = _read_tab_order_codes_sync(svc, REPORT_SHEET_ID, prev_tab)
        # Neu tab truoc da co du lieu thi has_prev_data = True
        has_prev_data = len(prev_codes) > 0

    # --- Ghi tab hom nay (9h30 / 13h30 / 17h30) ---
    tab_data = [
        [f"Cập nhật lúc: {time_str} ({label}) — PIC: {PIC_FILTER} — Mức ưu tiên: 1 (hôm nay), Cần làm gì: giao"],
        [],
        DETAIL_COLS,
    ] + _build_detail_rows(filtered_today)
    _clear_and_write(svc, REPORT_SHEET_ID, tab_name, tab_data)

    # --- Ghi tab Don_han_ngay_mai_ngay_mot (chi o 09:30 va 13:30) ---
    if label in ("09:30", "13:30") and filtered_next is not None:
        next_data = [
            [f"Cập nhật lúc: {time_str} ({label}) — PIC: {PIC_FILTER} — Mức ưu tiên: 2 (ngày mai) + 3 (ngày mốt), Cần làm gì: giao"],
            [],
            DETAIL_COLS,
        ] + _build_detail_rows(filtered_next)
        _clear_and_write(svc, REPORT_SHEET_ID, TAB_NEXT, next_data)

    log.info(f"[GiaoHang] Ghi xong sheet bao cao [{label}]")

    # Tra ve prev_codes va has_prev_data de dung tiep o tang tren
    return prev_codes, has_prev_data


async def write_report_sheet(
    label: str,
    filtered_today: list[dict],
    filtered_next: list[dict] | None,
    comparison_in: dict | None,
    now: datetime,
) -> tuple[bool, set[str], bool]:
    """
    Bat dong bo — chay trong asyncio thread pool.
    Tra ve (sheet_ok, prev_codes, has_prev_data).
    """
    if not SA_JSON:
        log.info("[GiaoHang] Khong co SA_JSON, bo qua ghi sheet.")
        return False, set(), False
    try:
        prev_codes, has_prev_data = await asyncio.to_thread(
            _write_report_sync,
            label, filtered_today, filtered_next, comparison_in, now
        )
        return True, prev_codes, has_prev_data
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()[-800:]
        log.error(f"[GiaoHang] Ghi sheet that bai:\n{err_detail}")
        try:
            chat_id = _get_chat_id()
            if chat_id and TELEGRAM_BOT_TOKEN:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": (
                                f"⚠️ <b>Không ghi được Google Sheet báo cáo [{label}]</b>\n"
                                f"<code>{err_detail[-600:]}</code>"
                            ),
                            "parse_mode": "HTML",
                        }
                    )
        except Exception:
            pass
        return False, set(), False


# =========================================================
# BUILD TIN NHAN TELEGRAM
# =========================================================
def _build_next_days_section(filtered_next: list[dict]) -> str:
    """Phan du kien don ngay mai / ngay mot."""
    total = len(filtered_next)
    return (
        f"\n\n📌 <b>Dự kiến đơn các ngày tiếp theo:</b>\n"
        f"Hiện tại, tổng số đơn hàng dự kiến giao trong ngày mai và ngày mốt là "
        f"<b>{total}</b> đơn. Kho kiểm tra xem có thể giao trước được không, "
        f"nhằm giảm tải sản lượng cho các ngày tiếp theo và hạn chế phát sinh tồn."
    )


def _build_comparison_section(comparison: dict, prev_label: str) -> str:
    """Phan so sanh don moi."""
    title = f"📌 <b>Đơn mới so với báo cáo {prev_label}:</b>"

    if not comparison.get("has_prev_data"):
        return (
            f"\n\n{title} "
            f"Không có dữ liệu {prev_label} để so sánh."
        )

    new_orders = comparison.get("new_orders", [])
    by_kho     = comparison.get("by_kho", {})

    if not new_orders:
        return f"\n\n{title} Không phát sinh đơn mới."

    lines = [f"\n\n{title}"]
    for kho, khach_map in sorted(by_kho.items()):
        total = sum(len(v) for v in khach_map.values())
        lines.append(f"• Kho <b>{kho}</b>: có thêm <b>{total}</b> đơn mới đến hạn giao.")
        for khach, orders in sorted(khach_map.items(), key=lambda x: -len(x[1])):
            lines.append(f"   - Khách {khach}: {len(orders)} đơn")
    return "\n".join(lines)


def build_message(
    label: str,
    filtered_today: list[dict],
    kho_summary: dict,
    sheet_ok: bool,
    now: datetime,
    filtered_next: list[dict] | None = None,
    comparison: dict | None = None,
) -> str:
    time_str  = now.strftime("%d/%m/%Y %H:%M")
    link_part = f"\n\n📄 <b>Link chi tiết:</b>\n{REPORT_SHEET_URL}"

    if not filtered_today:
        msg = (
            f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY ({label})</b>\n"
            f"PIC: {PIC_FILTER}\n"
            f"Thời gian: {time_str}\n\n"
            f"Hiện không có đơn cần giao trong hôm nay theo điều kiện lọc."
        )
        # Them phan du kien neu la 09:30 hoac 13:30
        if label in ("09:30", "13:30") and filtered_next is not None:
            msg += _build_next_days_section(filtered_next)
        # Them phan so sanh neu la 13:30 hoac 17:30
        if label in ("13:30", "17:30") and comparison:
            msg += _build_comparison_section(comparison, COMPARE_LABEL[label])
        msg += link_part
        return msg

    kho_lines = "\n".join(
        f"{i}. {kho}: <b>{cnt}</b> đơn"
        for i, (kho, cnt) in enumerate(kho_summary.items(), 1)
    )

    msg = (
        f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY ({label})</b>\n"
        f"PIC: {PIC_FILTER}\n"
        f"Thời gian: {time_str}\n\n"
        f"Tổng đơn cần giao hôm nay: <b>{len(filtered_today)}</b> đơn\n\n"
        f"📍 <b>Theo kho:</b>\n{kho_lines}"
    )

    # Them phan du kien neu la 09:30 hoac 13:30
    if label in ("09:30", "13:30") and filtered_next is not None:
        msg += _build_next_days_section(filtered_next)

    # Them phan so sanh neu la 13:30 hoac 17:30
    if label in ("13:30", "17:30") and comparison:
        msg += _build_comparison_section(comparison, COMPARE_LABEL[label])

    msg += link_part
    msg += (
        "\n\n<i>Yêu cầu: Các kho kiểm tra danh sách đơn, ưu tiên xử lý "
        "trong ngày và phản hồi nếu có đơn không giao được.</i>"
    )
    return msg


# =========================================================
# GUI TELEGRAM
# =========================================================
async def send_telegram(text: str) -> int | None:
    chat_id = _get_chat_id()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        log.error("[GiaoHang] Thieu TELEGRAM_BOT_TOKEN hoac chat ID")
        return None
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
            res = r.json()
            if res.get("ok"):
                return res.get("result", {}).get("message_id")
        log.error(f"[GiaoHang] Telegram loi {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        log.error(f"[GiaoHang] Telegram exception: {e}")
        return None


async def pin_telegram_message(message_id: int) -> bool:
    chat_id = _get_chat_id()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        log.error("[GiaoHang] Thieu TELEGRAM_BOT_TOKEN hoac chat ID khi pin tin nhan")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": True
            })
        if r.status_code == 200 and r.json().get("ok"):
            log.info(f"[GiaoHang] Pin tin nhan {message_id} thanh cong")
            return True
        log.error(
            f"Gửi báo cáo thành công nhưng pin tin nhắn thất bại. "
            f"Kiểm tra quyền admin của BOT. "
            f"(Telegram loi {r.status_code}: {r.text[:200]})"
        )
        return False
    except Exception as e:
        log.error(
            f"Gửi báo cáo thành công nhưng pin tin nhắn thất bại. "
            f"Kiểm tra quyền admin của BOT. (Exception: {e})"
        )
        return False


# =========================================================
# LOGIC CHINH
# =========================================================
async def run_giao_hang_report(label: str = "manual"):
    global _sent_today
    now   = datetime.now(TZ)
    today = now.date()

    if _sent_today.get(label) == today:
        log.info(f"[GiaoHang] Da gui [{label}] hom nay, bo qua.")
        return

    log.info(f"[GiaoHang] === BAT DAU [{label}] {now.strftime('%d/%m/%Y %H:%M')} ===")

    try:
        rows = await read_source_csv()

        # Loc don hom nay (priority=1)
        filtered_today = filter_rows_today(rows)
        kho_sum        = summarize_by_kho(filtered_today) if filtered_today else {}

        # Loc don ngay mai/ngay mot (chi can cho 09:30 va 13:30)
        filtered_next: list[dict] | None = None
        if label in ("09:30", "13:30"):
            filtered_next = filter_rows_next_days(rows)

        # Ghi sheet (dong thoi doc prev_codes tu tab truoc)
        sheet_ok, prev_codes, has_prev_data = await write_report_sheet(
            label        = label,
            filtered_today = filtered_today,
            filtered_next  = filtered_next,
            comparison_in  = None,
            now            = now,
        )

        # Xay dung comparison sau khi da doc duoc prev_codes tu sheet
        comparison: dict | None = None
        if label in ("13:30", "17:30"):
            comparison = find_new_orders_from_codes(
                current_filtered = filtered_today,
                prev_codes       = prev_codes,
                has_prev_data    = has_prev_data,
            )

        # Build va gui Telegram
        msg = build_message(
            label          = label,
            filtered_today = filtered_today,
            kho_summary    = kho_sum,
            sheet_ok       = sheet_ok,
            now            = now,
            filtered_next  = filtered_next,
            comparison     = comparison,
        )
        msg_id = await send_telegram(msg)

        if msg_id:
            _sent_today[label] = today
            log.info(f"[GiaoHang] XONG [{label}] — message_id={msg_id}")
            # Pin tat ca 3 moc
            pin_ok = await pin_telegram_message(msg_id)
            if not pin_ok:
                log.warning(f"[GiaoHang] Pin that bai [{label}], tiep tuc binh thuong.")
        else:
            log.error(f"[GiaoHang] Gui Telegram that bai [{label}]")

    except Exception as e:
        log.exception(f"[GiaoHang] Loi: {e}")
        try:
            await send_telegram(
                f"❌ <b>Bot GHN Giao Hàng lỗi [{label}]</b>\n"
                f"Thời gian: {now.strftime('%d/%m/%Y %H:%M')}\n"
                f"Lỗi: <code>{str(e)[:300]}</code>"
            )
        except Exception:
            pass


# =========================================================
# BACKGROUND LOOP
# =========================================================

# Luu vet trigger de tranh chay trung trong cung mot phut
_last_triggered: set = set()

async def run_giao_hang_scheduler():
    """Background task khoi dong cung FastAPI."""
    global _last_triggered
    log.info(f"[GiaoHang] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    log.info(f"[GiaoHang] Sheet nguon: {SOURCE_SPREADSHEET_ID} / GID={SOURCE_GID}")
    log.info(f"[GiaoHang] Sheet bao cao: {REPORT_SHEET_URL}")
    log.info(f"[GiaoHang] PIC: '{PIC_FILTER}'")
    log.info(f"[GiaoHang] Chat: {_get_chat_id() or '(chua cau hinh)'}")
    log.info(f"[GiaoHang] Sheets API: {'CO' if SA_JSON else 'KHONG (chi gui Telegram, khong ghi sheet)'}")

    SCHEDULE = [(9, 30, "09:30"), (13, 30, "13:30"), (17, 30, "17:30")]

    while True:
        try:
            now   = datetime.now(TZ)
            today = now.date()
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    trigger_key = (today, h, m)
                    if trigger_key not in _last_triggered:
                        _last_triggered.add(trigger_key)
                        # Don dep trigger key cu (ngay truoc)
                        _last_triggered = {k for k in _last_triggered if k[0] >= today}
                        log.info(f"[GiaoHang] Kich hoat scheduler cho khung gio {label}")
                        asyncio.create_task(run_giao_hang_report(label))
        except Exception as e:
            log.error(f"[GiaoHang] Loi loop: {e}")
        await asyncio.sleep(15)  # Kiem tra moi 15 giay de chinh xac hon
