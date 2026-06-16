"""
giao_hang_scheduler.py
=======================
Scheduler tu dong gui bao cao "don can giao hom nay" qua Telegram.
Chay cung FastAPI app nhu background task.

Lich: 09:30 va 13:30 hang ngay (Asia/Ho_Chi_Minh)
- 09:30: Ghi de sheet bao cao co dinh + gui Telegram + luu snapshot
- 13:30: Ghi de sheet bao cao co dinh + so sanh don moi vs 09:30 + gui Telegram

Sheet bao cao co dinh:
  REPORT_SHEET_ID = 1wpWMZRAaoaQXdmTL7dcKJ5PUFrmd8vESQmHj2ysNTHc
  (Phai share cho service account lam Editor truoc)

3 tab trong sheet bao cao:
  - "Tổng hợp theo kho"     (du lieu duoc ghi de moi lan chay)
  - "Chi tiết đơn"          (du lieu duoc ghi de moi lan chay)
  - "Đơn mới so với 09h30"  (chi cap nhat luc 13:30, xoa sach luc 09:30)
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
TZ           = ZoneInfo(TIMEZONE_STR)

PIC_FILTER      = os.environ.get("GIAO_HANG_PIC", "Nguyễn Minh Nghị")
ACTION_FILTER   = "giao"
PRIORITY_FILTER = "1: trong hôm nay"

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

# Ten 3 tab trong sheet bao cao
TAB_TONGHOP  = "Tổng hợp theo kho"
TAB_CHITIET  = "Chi tiết đơn"
TAB_DONMOI   = "Đơn mới so với 09h30"

# =========================================================
# TRANG THAI NOI BO
# =========================================================
# Snapshot 09:30: {date: {"orders": list, "order_codes": set}}
_morning_snapshot: dict = {}
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
    snapshot = _morning_snapshot.get(today)

    if snapshot is None:
        return {"has_morning_data": False, "new_orders": [], "by_kho": {}}

    morning_codes = snapshot["order_codes"]
    new_orders = [
        r for r in current_filtered
        if r["order"] and r["order"] not in morning_codes
    ]

    by_kho: dict = {}
    for r in new_orders:
        kho   = r["kho"] or "(Chưa xác định)"
        khach = r["khach"] or "(Chưa xác định)"
        by_kho.setdefault(kho, {}).setdefault(khach, []).append(r)

    log.info(f"[GiaoHang] Don moi (13:30 vs 09:30): {len(new_orders)}")
    return {"has_morning_data": True, "new_orders": new_orders, "by_kho": by_kho}


def save_morning_snapshot(filtered: list[dict], today: date):
    order_codes = {r["order"] for r in filtered if r["order"]}
    _morning_snapshot[today] = {"orders": filtered, "order_codes": order_codes}
    log.info(f"[GiaoHang] Luu snapshot 09:30: {len(order_codes)} order codes")
    # Xoa du lieu cu
    for d in [d for d in list(_morning_snapshot.keys()) if d < today]:
        del _morning_snapshot[d]


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
    # 1. Xoa toan bo du lieu cu
    svc.spreadsheets().values().clear(
        spreadsheetId=ss_id,
        range=f"'{tab}'!A1:Z10000",
    ).execute()

    # 2. Ghi du lieu moi
    if values:
        svc.spreadsheets().values().update(
            spreadsheetId=ss_id,
            range=f"'{tab}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    log.info(f"[GiaoHang] Ghi tab '{tab}': {len(values)} dong")


def _write_report_sync(filtered: list[dict], kho_summary: dict,
                       comparison: dict, now: datetime, is_afternoon: bool):
    """Dong bo — chay trong thread rieng."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    info  = json.loads(SA_JSON)
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    # Xac dinh cac tab can ton tai
    needed = [TAB_TONGHOP, TAB_CHITIET, TAB_DONMOI]
    _ensure_tabs_exist(svc, REPORT_SHEET_ID, needed)

    time_str = now.strftime("%d/%m/%Y %H:%M")
    label    = "13:30" if is_afternoon else "09:30"

    # --- Tab 1: Tong hop theo kho ---
    tab1 = [
        [f"Cập nhật lúc: {time_str} ({label})"],
        [],
        ["Kho hiện tại", "Số đơn cần giao hôm nay"],
    ]
    for kho, cnt in kho_summary.items():
        tab1.append([kho, cnt])
    tab1.append(["TỔNG CỘNG", len(filtered)])
    _clear_and_write(svc, REPORT_SHEET_ID, TAB_TONGHOP, tab1)

    # --- Tab 2: Chi tiet don ---
    tab2_h = [
        f"Cập nhật lúc: {time_str} ({label}) — "
        f"PIC: {PIC_FILTER} — Điều kiện: Mức ưu tiên=1, Cần làm gì=giao"
    ]
    tab2_cols = ["Mức độ ưu tiên", "Kho hiện tại", "PIC", "Order code",
                 "Cần làm gì", "Khách", "Địa chỉ giao", "Ngày nhập kho", "Đã lưu kho"]
    tab2 = [
        [tab2_h[0]],
        [],
        tab2_cols,
    ] + [
        [r["priority"], r["kho"], r["pic"], r["order"],
         r["action"], r["khach"], r["diachi"], r["ngay"], r["luukho"]]
        for r in filtered
    ]
    _clear_and_write(svc, REPORT_SHEET_ID, TAB_CHITIET, tab2)

    # --- Tab 3: Don moi so voi 09h30 ---
    if is_afternoon:
        new_orders = comparison.get("new_orders", [])
        has_data   = comparison.get("has_morning_data", False)

        if not has_data:
            tab3 = [["Không có dữ liệu 09:30 để so sánh."]]
        elif not new_orders:
            tab3 = [[f"Cập nhật lúc: {time_str}"], [],
                    ["Không phát sinh đơn mới so với báo cáo 09:30."]]
        else:
            tab3_cols = ["Kho hiện tại", "Khách", "Order code", "Cần làm gì",
                         "Mức độ ưu tiên", "Ngày nhập kho", "Đã lưu kho"]
            tab3 = [
                [f"Cập nhật lúc: {time_str} — {len(new_orders)} đơn mới"],
                [],
                tab3_cols,
            ] + [
                [r["kho"], r["khach"], r["order"], r["action"],
                 r["priority"], r["ngay"], r["luukho"]]
                for r in new_orders
            ]
        _clear_and_write(svc, REPORT_SHEET_ID, TAB_DONMOI, tab3)
    else:
        # 09:30: Xoa sach tab don moi (chuan bi cho 13:30)
        _clear_and_write(svc, REPORT_SHEET_ID, TAB_DONMOI,
                         [[f"Chờ dữ liệu 13:30 ({time_str})..."]])

    log.info(f"[GiaoHang] Ghi xong sheet bao cao [{label}]")


async def write_report_sheet(filtered, kho_summary, comparison, now, is_afternoon) -> bool:
    """Bat dong bo — chay trong asyncio thread pool."""
    if not SA_JSON:
        log.info("[GiaoHang] Khong co SA_JSON, bo qua ghi sheet.")
        return False
    try:
        await asyncio.to_thread(
            _write_report_sync,
            filtered, kho_summary, comparison, now, is_afternoon
        )
        return True
    except Exception as e:
        log.error(f"[GiaoHang] Ghi sheet that bai: {e}")
        return False


# =========================================================
# BUILD TIN NHAN TELEGRAM
# =========================================================
def _build_comparison_section(comparison: dict) -> str:
    if not comparison.get("has_morning_data"):
        return (
            "\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b> "
            "Không có dữ liệu 09:30 để so sánh."
        )

    new_orders = comparison.get("new_orders", [])
    by_kho     = comparison.get("by_kho", {})

    if not new_orders:
        return "\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b> Không phát sinh đơn mới."

    lines = ["\n\n📌 <b>Đơn mới so với báo cáo 09:30:</b>"]
    for kho, khach_map in sorted(by_kho.items()):
        total = sum(len(v) for v in khach_map.values())
        lines.append(f"• Kho <b>{kho}</b>: có thêm <b>{total}</b> đơn mới đến hạn giao.")
        for khach, orders in sorted(khach_map.items(), key=lambda x: -len(x[1])):
            lines.append(f"   - Khách {khach}: {len(orders)} đơn")
    return "\n".join(lines)


def build_message(filtered, kho_summary, sheet_ok, now,
                  comparison=None, is_afternoon=False) -> str:
    time_str = now.strftime("%d/%m/%Y %H:%M")
    label    = "13:30" if is_afternoon else "09:30"

    link_part = (
        f"\n\n📄 <b>Link chi tiết:</b>\n{REPORT_SHEET_URL}"
        if sheet_ok else ""
    )

    if not filtered:
        msg = (
            f"🚚 <b>BÁO CÁO ĐƠN CẦN GIAO HÔM NAY ({label})</b>\n"
            f"PIC: {PIC_FILTER}\n"
            f"Thời gian: {time_str}\n\n"
            f"Hiện không có đơn cần giao trong hôm nay theo điều kiện lọc."
        )
        if is_afternoon and comparison:
            msg += _build_comparison_section(comparison)
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
        f"Tổng đơn cần giao: <b>{len(filtered)}</b> đơn\n\n"
        f"📍 <b>Theo kho:</b>\n{kho_lines}"
    )

    if is_afternoon and comparison:
        msg += _build_comparison_section(comparison)

    msg += link_part
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

        comparison = find_new_orders(filtered, today) if is_afternoon else None

        # Ghi de len sheet bao cao co dinh
        sheet_ok = await write_report_sheet(
            filtered, kho_sum, comparison or {}, now, is_afternoon
        )

        # Build va gui Telegram
        msg = build_message(
            filtered, kho_sum, sheet_ok, now,
            comparison=comparison, is_afternoon=is_afternoon
        )
        ok = await send_telegram(msg)

        if ok:
            _sent_today[label] = today
            if label == "09:30":
                save_morning_snapshot(filtered, today)
            log.info(f"[GiaoHang] XONG [{label}]")
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
async def run_giao_hang_scheduler():
    """Background task khoi dong cung FastAPI."""
    log.info(f"[GiaoHang] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    log.info(f"[GiaoHang] Sheet nguon: {SOURCE_SPREADSHEET_ID} / GID={SOURCE_GID}")
    log.info(f"[GiaoHang] Sheet bao cao: {REPORT_SHEET_URL}")
    log.info(f"[GiaoHang] PIC: '{PIC_FILTER}'")
    log.info(f"[GiaoHang] Chat: {_get_chat_id() or '(chua cau hinh)'}")
    log.info(f"[GiaoHang] Sheets API: {'CO' if SA_JSON else 'KHONG (chi gui Telegram, khong ghi sheet)'}")

    SCHEDULE = [(9, 30, "09:30"), (13, 30, "13:30")]

    while True:
        try:
            now = datetime.now(TZ)
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    await run_giao_hang_report(label)
        except Exception as e:
            log.error(f"[GiaoHang] Loi loop: {e}")
        await asyncio.sleep(60)
