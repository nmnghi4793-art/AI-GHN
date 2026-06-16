import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from collect_money_bot import run_collect_money_check

log = logging.getLogger("collect_money_scheduler")

TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TIMEZONE_STR)

# Lưu vết để tránh trùng lặp
_sent_today = {}
_last_triggered = set()

async def run_collect_money_report(label: str = "manual"):
    global _sent_today
    now = datetime.now(TZ)
    today = now.date()
    
    if _sent_today.get(label) == today:
        log.info(f"[CollectMoney] Da gui bao cao [{label}] hom nay, bo qua.")
        return
        
    log.info(f"[CollectMoney] === BAT DAU [{label}] {now.strftime('%d/%m/%Y %H:%M')} ===")
    
    try:
        # Chạy bot để cào và gửi tin nhắn
        success = await run_collect_money_check()
        if success:
            _sent_today[label] = today
            log.info(f"[CollectMoney] XONG gui bao cao [{label}]")
        else:
            log.error(f"[CollectMoney] Bot bao loi hoac ket noi that bai [{label}]")
    except Exception as e:
        log.exception(f"[CollectMoney] Loi xay ra khi chay scheduler [{label}]: {e}")

async def run_collect_money_scheduler():
    global _last_triggered
    log.info(f"[CollectMoney] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    
    SCHEDULE = [(21, 30, "21:30"), (22, 30, "22:30")]
    
    while True:
        try:
            now = datetime.now(TZ)
            today = now.date()
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    trigger_key = (today, h, m)
                    if trigger_key not in _last_triggered:
                        _last_triggered.add(trigger_key)
                        # Dọn dẹp các trigger key cũ của những ngày trước để tránh tràn bộ nhớ
                        _last_triggered = {k for k in _last_triggered if k[0] >= today}
                        
                        log.info(f"[CollectMoney] Kich hoat scheduler cho khung gio {label}")
                        asyncio.create_task(run_collect_money_report(label))
        except Exception as e:
            log.error(f"[CollectMoney] Loi loop scheduler: {e}")
            
        await asyncio.sleep(15) # Check check mỗi 15 giây để chính xác hơn
