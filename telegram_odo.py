import os
import sys
import httpx
import asyncio
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import odo_monitor

# Read Telegram configuration from environment variables or fallbacks
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("VANHANH_BOT_TOKEN") or "7854890675:AAHVb2aL_8WjE5wN5v0Z1M2K3L4P5Q6R7S8"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("VANHANH_CHAT_ID") or "-1002345678901"

async def send_telegram_message(text: str) -> bool:
    """Helper gửi message Telegram qua httpx async."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("VANHANH_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("VANHANH_CHAT_ID")
    
    if not token or not chat_id:
        print("[TELEGRAM ODO] Skipping send: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        print(f"[TELEGRAM ODO PREVIEW]\n{text}\n")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                print("[TELEGRAM ODO] Sent message successfully!")
                return True
            else:
                print(f"[TELEGRAM ODO ERROR] Telegram API returned status {res.status_code}: {res.text}")
                return False
    except Exception as e:
        print(f"[TELEGRAM ODO ERROR] Failed to send telegram message: {e}")
        return False

def build_xe_van_hanh_message(target_date: str) -> str:
    """Xây dựng tin nhắn 🚚 XE VẬN HÀNH (Xe OFF & Xe tăng cường) dành cho mốc 18:00."""
    xe_off_map, xe_tc_map = odo_monitor.get_xe_daily_breakdown(target_date)
    
    if not xe_off_map and not xe_tc_map:
        return ""

    msg = f"🚚 *XE VẬN HÀNH*\nNgày {target_date}\n\n"
    
    if xe_off_map:
        msg += "*Xe OFF*\n"
        for k, v in xe_off_map.items():
            short_name = k.replace("Kho Giao Hàng Nặng -", "").strip()
            msg += f"• {short_name}: {v} xe\n"
        msg += "\n"

    if xe_tc_map:
        msg += "*Xe tăng cường*\n"
        for k, v in xe_tc_map.items():
            short_name = k.replace("Kho Giao Hàng Nặng -", "").strip()
            msg += f"• {short_name}: {v} xe\n"

    return msg.strip()

def build_odo_report_message(multi_date_statuses: dict, slot_hour: int = 18) -> str:
    """
    Xây dựng tin nhắn cảnh báo ODO cho một hoặc nhiều ngày.
    multi_date_statuses: dict mapping date_str -> odo_status_dict
    """
    # Check if all dates are fully completed
    all_completed = True
    for d_str, status_obj in multi_date_statuses.items():
        if status_obj["summary"]["thieu_khos"] > 0 or status_obj["summary"]["total_xe_thua"] > 0:
            all_completed = False
            break

    if all_completed:
        # Nếu tất cả các ngày đều đủ
        if slot_hour in [19, 21, 23]:
            dates_label = ", ".join(multi_date_statuses.keys())
            return f"✅ *Toàn bộ kho đã nhập đầy đủ ODO ngày {dates_label}*"
        return ""

    # Có kho chưa đủ hoặc báo thừa
    latest_date = list(multi_date_statuses.keys())[-1]
    msg = f"🚨 *BÁO CÁO ODO*\nNgày {latest_date}\n\n"

    # 1. Gom nhóm các kho thiếu ODO
    thieu_list = []
    thua_list = []

    for d_str, status_obj in multi_date_statuses.items():
        for item in status_obj["details"]:
            kho = item["kho"]
            short_kho = kho.replace("Kho Giao Hàng Nặng -", "").strip()
            if item["status"] == "THIEU":
                thieu_list.append((short_kho, d_str, item["actual_odo"], item["expected_odo"], item["diff"]))
            elif item["status"] == "THUA":
                thua_list.append((short_kho, d_str, item["actual_odo"], item["expected_odo"], item["diff"]))

    if thieu_list:
        msg += "❌ *Các kho chưa báo đủ ODO*\n"
        # Gom nhóm kho nếu báo nhiều ngày
        kho_groups = {}
        for short_kho, d_str, act, exp, diff in thieu_list:
            if short_kho not in kho_groups:
                kho_groups[short_kho] = []
            kho_groups[short_kho].append((d_str, act, exp, diff))

        for short_kho, items in kho_groups.items():
            msg += f"• *Kho {short_kho}*\n"
            if len(items) == 1 and len(multi_date_statuses) == 1:
                d_str, act, exp, diff = items[0]
                msg += f"  Đã báo: {act} | Phải báo: {exp} | Thiếu: {diff} xe\n"
            else:
                for d_str, act, exp, diff in items:
                    msg += f"  {d_str}: Thiếu {diff} xe (Đã báo: {act}/{exp})\n"
        msg += "\n"

    if thua_list:
        msg += "➕ *Các kho báo thừa ODO*\n"
        for short_kho, d_str, act, exp, diff in thua_list:
            msg += f"• *Kho {short_kho}*\n"
            msg += f"  Đã báo: {act} | Phải báo: {exp} | Thừa: {diff} xe\n"

    return msg.strip()
