import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import odo_monitor
import telegram_odo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("odo_scheduler")

LOGS_FILE = os.path.join(BASE_DIR, "scratch", "odo_monitor_logs.json")

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
        # Giữ tối đa 500 bản ghi log gần nhất
        trimmed = log_entries[-500:] if len(log_entries) > 500 else log_entries
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Failed to save odo logs: {e}")

def record_check_logs(status_obj: dict, sent_telegram: bool, slot_name: str):
    """Ghi vết kết quả kiểm tra vào file odo_monitor_logs.json."""
    logs = load_logs()
    target_date = status_obj["summary"]["target_date"]
    check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in status_obj["details"]:
        logs.append({
            "check_id": f"{target_date}_{item['kho']}_{int(datetime.now().timestamp())}",
            "ngay": target_date,
            "kho": item["kho"],
            "tong_xe": item["tong_xe"],
            "xe_off": item["xe_off"],
            "xe_tc": item["xe_tc"],
            "expected_odo": item["expected_odo"],
            "actual_odo": item["actual_odo"],
            "thieu": item["diff"] if item["status"] == "THIEU" else 0,
            "thua": item["diff"] if item["status"] == "THUA" else 0,
            "status": item["status"],
            "check_time": check_time,
            "slot_name": slot_name,
            "sent_telegram": sent_telegram
        })
    save_logs(logs)

async def check_and_notify_odo(slot_name: str = "MANUAL", force_refresh: bool = True):
    """
    Thực hiện 1 chu kỳ đối soát ODO và gửi Telegram nếu đạt điều kiện.
    """
    now_dt = datetime.now()
    today_str = now_dt.strftime("%d/%m/%Y")
    
    # 1. Tính toán ODO ngày hôm nay
    today_status = odo_monitor.calculate_odo_status(today_str, force_refresh=force_refresh)
    
    # 2. Kiểm tra nếu có các ngày trước (N-1, N-2...) chưa đủ ODO
    multi_date_statuses = {}
    
    # Check back 3 days
    for days_back in range(3, 0, -1):
        prev_date = (now_dt - timedelta(days=days_back)).strftime("%d/%m/%Y")
        prev_status = odo_monitor.calculate_odo_status(prev_date, force_refresh=False)
        if prev_status["summary"]["thieu_khos"] > 0:
            multi_date_statuses[prev_date] = prev_status

    multi_date_statuses[today_str] = today_status

    slot_hour = now_dt.hour
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

    # 5. Lưu log đối soát
    record_check_logs(today_status, sent_telegram=sent_any, slot_name=slot_name)
    return today_status

async def run_odo_scheduler():
    """
    Vòng lặp Railway Scheduler kiểm tra ODO tự động.
    Lịch cố định: 18:00, 19:00, 21:00, 23:00.
    Nếu ngày N lúc 23h còn thiếu ODO -> Ngày N+1 nhắc nhở 2 tiếng/lần (07h -> 23h).
    """
    log.info("[ODO SCHEDULER] Engine initialized. Monitoring slots (18h, 19h, 21h, 23h & N+1 reminders)...")
    
    last_executed_slot = None

    while True:
        try:
            now_dt = datetime.now()
            hour = now_dt.hour
            minute = now_dt.minute
            today_str = now_dt.strftime("%Y-%m-%d")

            # Slot key to prevent duplicate runs within the same minute/slot
            current_slot_key = f"{today_str}_{hour}:{minute}"

            # Check standard fixed slots (18:00, 19:00, 21:00, 23:00) at top of the hour (minute 0..2)
            is_fixed_slot = (hour in [18, 19, 21, 23]) and (minute < 3)

            # Check N+1 reminder slots (07:00, 09:00, 11:00, 13:00, 15:00, 17:00, 19:00, 21:00, 23:00)
            is_reminder_slot = (hour in [7, 9, 11, 13, 15, 17, 19, 21, 23]) and (minute < 3)

            if (is_fixed_slot or is_reminder_slot) and (current_slot_key != last_executed_slot):
                last_executed_slot = current_slot_key
                slot_label = f"FIXED_{hour}:00" if is_fixed_slot else f"REMINDER_{hour}:00"
                log.info(f"[ODO SCHEDULER] Triggering check for slot {slot_label}...")
                await check_and_notify_odo(slot_name=slot_label, force_refresh=True)

        except Exception as e:
            log.error(f"[ODO SCHEDULER ERROR] Loop error: {e}")

        # Check every 30 seconds
        await asyncio.sleep(30)
