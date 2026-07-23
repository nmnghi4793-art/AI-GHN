import os
import sys
import httpx
import asyncio
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import odo_monitor

# Lock ODO Chat ID strictly to -1002712779761
ODO_CHAT_ID = os.environ.get("ODO_CHAT_ID", "-1002712779761")
ODO_SHEET_ID = os.environ.get("ODO_SHEET_ID", "1xi9wAxHZktDROLcZHxQF5dvp6grzfB1mSkVw5gpWUeo")

def get_odo_bot_token() -> str:
    """Ưu tiên lấy ODO_BOT_TOKEN từ Railway Variable, sau đó là TELEGRAM_BOT_TOKEN hoặc fallback."""
    return (
        os.environ.get("ODO_BOT_TOKEN") or
        os.environ.get("TELEGRAM_BOT_TOKEN") or
        os.environ.get("VANHANH_BOT_TOKEN") or
        "8969802246:AAElLvlCeHSgBNnKHNh5ytZbIR-1iyWtD7g"
    )

def get_vn_datetime() -> datetime:
    """Trả về datetime theo múi giờ Việt Nam (Asia/Ho_Chi_Minh / UTC+7)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=7)

async def send_telegram_message(text: str, target_chat_id: str = None) -> tuple:
    """
    Helper gửi message Telegram.
    Chỉ gửi vào đúng Chat Group -1002712779761 qua Bot @ODOMienTrung_Bot (ODO_BOT_TOKEN).
    Returns: (success: bool, detail_message: str)
    """
    chat_id = target_chat_id or ODO_CHAT_ID  # Chat ID -1002712779761
    token = get_odo_bot_token()

    if not token:
        print("[TELEGRAM ODO] Skipping send: BOT TOKEN missing.")
        return False, "Chưa cấu hình biến môi trường ODO_BOT_TOKEN trên Railway cho @ODOMienTrung_Bot."

    vn_now = get_vn_datetime()
    print(f"[TELEGRAM ODO LOG] [{vn_now.strftime('%H:%M:%S %d/%m/%Y')}] Sending message to target chat_id={chat_id}...")

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
                print(f"[TELEGRAM ODO SUCCESS] Sent message to chat_id={chat_id} (HTTP 200 OK)")
                return True, "Gửi tin nhắn Telegram thành công!"
            else:
                payload_plain = {
                    "chat_id": chat_id,
                    "text": text.replace("*", "").replace("`", "").replace("_", ""),
                    "disable_web_page_preview": True
                }
                res2 = await client.post(url, json=payload_plain)
                if res2.status_code == 200:
                    print(f"[TELEGRAM ODO SUCCESS] Sent fallback plain text message to chat_id={chat_id} (HTTP 200 OK)")
                    return True, "Gửi tin nhắn Telegram (Plain text) thành công!"
                else:
                    err_text = res2.text
                    print(f"[TELEGRAM ODO ERROR] Telegram API returned status {res2.status_code}: {err_text}")
                    if "chat not found" in err_text.lower():
                        return False, "Bot chưa nằm trong nhóm ID -1002712779761. Vui lòng thêm @ODOMienTrung_Bot vào nhóm hoặc nhập Token của @ODOMienTrung_Bot vào biến ODO_BOT_TOKEN trên Railway!"
                    elif "unauthorized" in err_text.lower():
                        return False, "Token Bot Telegram không hợp lệ. Vui lòng nhập đúng Token của @ODOMienTrung_Bot vào biến ODO_BOT_TOKEN trên Railway!"
                    return False, f"Telegram API báo lỗi HTTP {res2.status_code}: {err_text}"
    except Exception as e:
        print(f"[TELEGRAM ODO ERROR] Failed to send telegram message: {e}")
        return False, f"Ngoại lệ kết nối Telegram: {e}"

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
    all_completed = True
    for d_str, status_obj in multi_date_statuses.items():
        if status_obj["summary"]["thieu_khos"] > 0 or status_obj["summary"]["total_xe_thua"] > 0:
            all_completed = False
            break

    if all_completed:
        if slot_hour in [19, 21, 23]:
            dates_label = ", ".join(multi_date_statuses.keys())
            return f"✅ *Toàn bộ kho đã nhập đầy đủ ODO ngày {dates_label}*"
        return ""

    latest_date = list(multi_date_statuses.keys())[-1]
    msg = f"🚨 *BÁO CÁO ODO*\nNgày {latest_date}\n\n"

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
                    msg += f"  - Ngày {d_str}: Đã báo {act}/{exp} (Thiếu {diff} xe)\n"
        msg += "\n"

    if thua_list:
        msg += "➕ *Các kho báo THỪA ODO*\n"
        for short_kho, d_str, act, exp, diff in thua_list:
            msg += f"• *Kho {short_kho}*: Đã báo {act}/{exp} (Thừa {diff} xe)\n"

    return msg.strip()
