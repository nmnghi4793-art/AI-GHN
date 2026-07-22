import os
import sys
import json
import asyncio
import logging
import httpx
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import odo_monitor
import telegram_odo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("odo_scheduler")

LOGS_FILE = os.path.join(BASE_DIR, "scratch", "odo_monitor_logs.json")

LAST_RUN_INFO = {
    "last_run_time": "--",
    "target_date": "--",
    "total_khos": 0,
    "status": "Khởi tạo"
}

def get_vn_datetime() -> datetime:
    """Trả về datetime theo múi giờ Việt Nam (Asia/Ho_Chi_Minh / UTC+7)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=7)

def get_next_run_time() -> str:
    """Tính toán thời gian báo cáo ODO tiếp theo."""
    vn_now = get_vn_datetime()
    slots = [7, 9, 11, 13, 15, 17, 18, 19, 21, 23]

    next_dt = None
    for h in slots:
        slot_dt = vn_now.replace(hour=h, minute=0, second=0, microsecond=0)
        if slot_dt > vn_now:
            next_dt = slot_dt
            break

    if not next_dt:
        tomorrow = vn_now + timedelta(days=1)
        next_dt = tomorrow.replace(hour=7, minute=0, second=0, microsecond=0)

    return next_dt.strftime("%H:%M %d/%m/%Y")

def load_logs() -> list:
    """Đọc lịch sử kiểm tra ODO."""
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_logs(log_entries: list):
    """Lưu lịch sử kiểm tra ODO."""
    try:
        os.makedirs(os.path.dirname(LOGS_FILE), exist_ok=True)
        trimmed = log_entries[-500:] if len(log_entries) > 500 else log_entries
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Failed to save odo logs: {e}")

def record_check_logs(status_obj: dict, sent_telegram: bool, slot_name: str):
    """Ghi vết kết quả kiểm tra vào file odo_monitor_logs.json."""
    logs = load_logs()
    target_date = status_obj["summary"]["target_date"]
    vn_now = get_vn_datetime()
    check_time = vn_now.strftime("%Y-%m-%d %H:%M:%S")

    is_test = odo_monitor.is_before_golive(target_date)

    for item in status_obj["details"]:
        logs.append({
            "check_id": f"{target_date}_{item['kho']}_{int(vn_now.timestamp())}",
            "ngay": target_date,
            "kho": item["kho"],
            "tong_xe": item["tong_xe"],
            "xe_off": item["xe_off"],
            "xe_tc": item["xe_tc"],
            "expected_odo": item["expected_odo"],
            "actual_odo": item["actual_odo"],
            "thieu": 0 if is_test else (item["diff"] if item["status"] == "THIEU" else 0),
            "thua": item["diff"] if item["status"] == "THUA" else 0,
            "status": "TEST / IGNORED" if is_test else item["status"],
            "check_time": check_time,
            "slot_name": slot_name,
            "sent_telegram": sent_telegram
        })
    save_logs(logs)

async def check_and_notify_odo(slot_name: str = "MANUAL", force_refresh: bool = True):
    """
    Thực hiện 1 chu kỳ đối soát ODO và gửi Telegram nếu đạt điều kiện.
    Gửi ĐÚNG vào chat group -1002712779761.
    Cấu hình GO-LIVE: Chỉ xử lý và nhắc nhở từ 23/07/2026 trở đi.
    """
    global LAST_RUN_INFO
    vn_now = get_vn_datetime()
    today_str = vn_now.strftime("%d/%m/%Y")
    now_str = vn_now.strftime("%H:%M:%S %d/%m/%Y")

    log.info(f"========== [ODO SCHEDULER RUN] {now_str} (ICT Asia/Ho_Chi_Minh) ==========")
    log.info(f"1. Slot execution: {slot_name}")
    log.info(f"2. Target checking date: {today_str} (GO-LIVE DATE: 23/07/2026)")
    log.info(f"3. Target Telegram Chat ID: {telegram_odo.ODO_CHAT_ID}")

    # 1. Tính toán ODO ngày hôm nay
    today_status = odo_monitor.calculate_odo_status(today_str, force_refresh=force_refresh)
    summary = today_status["summary"]

    LAST_RUN_INFO = {
        "last_run_time": now_str,
        "target_date": today_str,
        "total_khos": summary["total_khos"],
        "status": f"Hoàn thành ({summary['du_khos']}/{summary['total_khos']} kho đủ)"
    }

    log.info(f"4. Total ODO rows matched: {summary['total_khos']} master warehouses")
    log.info(f"5. Warehouses status: Sufficient={summary['du_khos']}, Deficit={summary['thieu_khos']}, Surplus={summary['total_xe_thua']} xe")
    log.info(f"6. Total xe missing ODO: {summary['total_xe_thieu']} xe")

    # Kiểm tra Go-Live Date: Nếu ngày hiện tại < 23/07/2026 thì xem là dữ liệu TEST, KHÔNG GỬI TELEGRAM CẢNH BÁO
    if odo_monitor.is_before_golive(today_str) and "COMMAND" not in slot_name:
        log.info(f"[ODO GO-LIVE FILTER] Date {today_str} is before GO-LIVE date (23/07/2026). Skipping Telegram alerts & reminders.")
        record_check_logs(today_status, sent_telegram=False, slot_name=f"{slot_name}_TEST_IGNORED")
        return today_status

    # 2. Kiểm tra các ngày trước chưa đủ ODO (CHỈ XEM CÁC NGÀY >= 23/07/2026)
    multi_date_statuses = {}
    for days_back in range(3, 0, -1):
        prev_date = (vn_now - timedelta(days=days_back)).strftime("%d/%m/%Y")
        if odo_monitor.is_before_golive(prev_date):
            continue  # Bỏ qua toàn bộ dữ liệu trước Go-Live 23/07/2026
        prev_status = odo_monitor.calculate_odo_status(prev_date, force_refresh=False)
        if prev_status["summary"]["thieu_khos"] > 0:
            multi_date_statuses[prev_date] = prev_status

    multi_date_statuses[today_str] = today_status

    slot_hour = vn_now.hour
    sent_any = False

    # 3. Ở mốc 18:00: Gửi tin nhắn XE VẬN HÀNH (OFF & TC)
    if slot_hour == 18 or "18:00" in slot_name:
        msg_xe = telegram_odo.build_xe_van_hanh_message(today_str)
        if msg_xe:
            await telegram_odo.send_telegram_message(msg_xe)

    # 4. Gửi báo cáo ODO
    msg_report = telegram_odo.build_odo_report_message(multi_date_statuses, slot_hour=slot_hour)
    if msg_report:
        sent_any = await telegram_odo.send_telegram_message(msg_report)

    next_time_str = get_next_run_time()
    log.info(f"7. Telegram send result: {'SUCCESS (200 OK)' if sent_any else 'COMPLETED / LOGGED'}")
    log.info(f"8. Next scheduled run time: {next_time_str}")

    # 5. Lưu log đối soát
    record_check_logs(today_status, sent_telegram=sent_any, slot_name=slot_name)
    return today_status

async def process_telegram_command(command: str, chat_id: str) -> str:
    """
    Xử lý các lệnh Telegram (/ping, /status, /odo, /testodo, /next, /sendtest).
    Chỉ trả lời cho chat ID -1002712779761.
    """
    if str(chat_id) != str(telegram_odo.ODO_CHAT_ID):
        log.info(f"[ODO BOT FILTER] Ignored command from unauthorized chat_id={chat_id}")
        return ""

    cmd = command.strip().lower().split("@")[0]
    vn_now = get_vn_datetime()
    now_str = vn_now.strftime("%d/%m/%Y %H:%M")

    if cmd == "/ping":
        return (
            "✅ *BOT ODO đang hoạt động*\n"
            f"🕒 *Server Time:* {now_str}\n"
            "📍 *Timezone:* Asia/Ho_Chi_Minh\n"
            "🚀 *Go-Live Date:* 23/07/2026"
        )
    elif cmd == "/status":
        next_run = get_next_run_time()
        last_time = LAST_RUN_INFO.get("last_run_time", "--")
        total_k = LAST_RUN_INFO.get("total_khos", 25)
        return (
            "📊 *TRẠNG THÁI BOT ODO*\n"
            "• *Scheduler:* 🟢 Đang hoạt động\n"
            "• *Ngày Go-Live:* `23/07/2026`\n"
            f"• *Mốc chạy tiếp theo:* {next_run}\n"
            f"• *Chat ID hiện tại:* `{telegram_odo.ODO_CHAT_ID}`\n"
            f"• *Sheet đang đọc:* `{telegram_odo.ODO_SHEET_ID}`\n"
            f"• *Số kho đã kiểm tra:* {total_k}/25 kho\n"
            f"• *Thời gian chạy gần nhất:* {last_time}"
        )
    elif cmd in ["/odo", "/testodo"]:
        await check_and_notify_odo(slot_name="COMMAND_ODO", force_refresh=True)
        return "✅ *Đã thực hiện kiểm tra ODO ngay lập tức và gửi báo cáo vào group.*"
    elif cmd == "/next":
        next_run = get_next_run_time()
        return f"Lần báo cáo tiếp theo:\n*{next_run}*"
    elif cmd == "/sendtest":
        await telegram_odo.send_telegram_message("✅ *BOT ODO đã kết nối đúng bot và đúng group.*")
        return "✅ *Đã gửi tin nhắn test kết nối vào group.*"

    return ""

async def run_odo_telegram_bot_polling():
    """
    Vòng lặp duy nhất (Single Instance Polling) cho ODO Telegram Bot.
    """
    token = telegram_odo.get_odo_bot_token()
    if not token:
        log.error("[ODO BOT ERROR] TELEGRAM_BOT_TOKEN / ODO_BOT_TOKEN missing!")
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            del_res = await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook", json={"drop_pending_updates": True})
            log.info(f"[ODO BOT] Reset Webhook result: {del_res.json()}")
        except Exception as e:
            log.warning(f"[ODO BOT] deleteWebhook failed: {e}")

        bot_username = "ODOMienTrung_Bot"
        try:
            me_res = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if me_res.status_code == 200:
                bot_info = me_res.json().get("result", {})
                bot_username = bot_info.get("username", bot_username)
        except Exception as me_err:
            log.warning(f"[ODO BOT] getMe error: {me_err}")

        log.info("==========================================================================")
        log.info("[ODO BOT] BOT started")
        log.info(f"[ODO BOT] Telegram username: @{bot_username}")
        log.info(f"[ODO BOT] Allowed Chat ID: {telegram_odo.ODO_CHAT_ID}")
        log.info("[ODO BOT] Mode: Polling (Single Instance)")
        log.info("[ODO BOT] Go-Live Date: 23/07/2026")
        log.info("[ODO BOT] Registered Commands: /odo, /ping, /status, /next, /testodo, /sendtest")
        log.info("==========================================================================")

        url = f"https://api.telegram.org/bot{token}/getUpdates"
        offset = 0

        while True:
            try:
                res = await client.get(url, params={"offset": offset, "timeout": 5, "allowed_updates": ["message", "edited_message"]})
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        text = msg.get("text", "").strip()
                        chat_id = msg.get("chat", {}).get("id")

                        if text.startswith("/") and chat_id:
                            log.info(f"[ODO BOT COMMAND] Received '{text}' from chat_id={chat_id}")
                            resp_text = await process_telegram_command(text, chat_id=str(chat_id))
                            if resp_text:
                                await telegram_odo.send_telegram_message(resp_text)
                elif res.status_code == 409:
                    log.warning("[ODO BOT 409] Detected duplicate polling instance. Sleeping 5s before retrying...")
                    await asyncio.sleep(5)
            except Exception:
                pass

            await asyncio.sleep(2)

async def run_odo_scheduler():
    """
    Vòng lặp Railway Scheduler kiểm tra ODO tự động.
    Lịch cố định: 18:00, 19:00, 21:00, 23:00 (múi giờ ICT Asia/Ho_Chi_Minh).
    CHỈ KIỂM TRA VÀ BÁO CÁO TỪ 23/07/2026 TRỞ ĐI.
    """
    log.info("[ODO SCHEDULER] Engine initialized with timezone Asia/Ho_Chi_Minh (UTC+7). GO-LIVE DATE: 23/07/2026...")

    asyncio.create_task(run_odo_telegram_bot_polling())

    last_executed_slot = None

    while True:
        try:
            vn_now = get_vn_datetime()
            hour = vn_now.hour
            minute = vn_now.minute
            today_str = vn_now.strftime("%Y-%m-%d")

            current_slot_key = f"{today_str}_{hour}:{minute}"

            # Fixed slots (18:00, 19:00, 21:00, 23:00)
            is_fixed_slot = (hour in [18, 19, 21, 23]) and (minute < 3)

            # N+1 reminder slots (07:00 -> 23:00 every 2h)
            is_reminder_slot = (hour in [7, 9, 11, 13, 15, 17, 19, 21, 23]) and (minute < 3)

            if (is_fixed_slot or is_reminder_slot) and (current_slot_key != last_executed_slot):
                last_executed_slot = current_slot_key
                slot_label = f"FIXED_{hour}:00" if is_fixed_slot else f"REMINDER_{hour}:00"
                log.info(f"[ODO SCHEDULER] Triggering check for ICT slot {slot_label}...")
                await check_and_notify_odo(slot_name=slot_label, force_refresh=True)

        except Exception as e:
            log.error(f"[ODO SCHEDULER ERROR] Loop error: {e}")

        await asyncio.sleep(30)
