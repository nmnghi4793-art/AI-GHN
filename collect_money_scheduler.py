import os
import sys
import io
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collect_money_bot import run_collect_money_check

def load_env():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
        current_dir = os.path.dirname(current_dir)

load_env()

# Configure logging to console & file
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "collect_money_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("collect_money_scheduler")

TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TIMEZONE_STR)

# Lưu vết để tránh trùng lặp
_sent_today = {}
_last_triggered = set()

def log_next_run(now, schedule):
    next_runs = []
    for h, m, label in schedule:
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        next_runs.append(candidate)
    next_run = min(next_runs)
    log.info(f"Lần kiểm tra tiếp theo lúc: {next_run.strftime('%H:%M')}")

async def run_collect_money_report(label: str = "manual"):
    global _sent_today
    now = datetime.now(TZ)
    today = now.date()
    
    if label != "manual" and _sent_today.get(label) == today:
        log.info(f"[CollectMoney] Da gui bao cao [{label}] hom nay, bo qua.")
        return
        
    log.info(f"[CollectMoney] === BAT DAU [{label}] {now.strftime('%d/%m/%Y %H:%M')} ===")
    
    try:
        # Chạy bot để cào và gửi tin nhắn
        success = await run_collect_money_check()
        if success:
            if label != "manual":
                _sent_today[label] = today
            log.info(f"[CollectMoney] XONG gui bao cao [{label}]")
        else:
            log.error(f"[CollectMoney] Bot bao loi hoac ket noi that bai [{label}]")
    except Exception as e:
        log.exception(f"[CollectMoney] Loi xay ra khi chay scheduler [{label}]: {e}")

async def run_collect_money_scheduler():
    global _last_triggered
    
    # Tự động vô hiệu hóa nếu chạy trên Cloud (Linux) hoặc có cấu hình tắt
    is_disabled_env = os.environ.get("DISABLE_COLLECT_MONEY_SCHEDULER", "").lower() == "true"
    is_polling_disabled = os.environ.get("DISABLE_TELEGRAM_POLLING", "").lower() == "true"
    is_cloud = os.name != "nt"  # nt đại diện cho Windows local
    
    if is_disabled_env or is_polling_disabled or is_cloud:
        log.info("[CollectMoney] Scheduler bị vô hiệu hóa (chạy trên Cloud/Linux hoặc cấu hình tắt).")
        return

    log.info(f"[CollectMoney] Scheduler khoi dong (TZ={TIMEZONE_STR})")
    
    # Gửi thử tin nhắn test khởi động (Yêu cầu 3)
    log.info("Đang gửi thử tin nhắn test khởi động Telegram...")
    from collect_money_bot import send_telegram_message
    sent_test = await send_telegram_message("BOT báo cáo thu tiền/bắn kiểm đã khởi động thành công.")
    if not sent_test:
        log.error("Không thể gửi tin nhắn test khởi động. Vui lòng kiểm tra lại cấu hình Telegram.")
        
    SCHEDULE = [(21, 30, "21:30"), (22, 30, "22:30"), (23, 0, "23:00")]
    
    # Log lần chạy tiếp theo lúc khởi động
    log_next_run(datetime.now(TZ), SCHEDULE)
    
    while True:
        try:
            now = datetime.now(TZ)
            today = now.date()
            for h, m, label in SCHEDULE:
                if now.hour == h and now.minute == m:
                    trigger_key = (today, h, m)
                    if trigger_key not in _last_triggered:
                        _last_triggered.add(trigger_key)
                        _last_triggered = {k for k in _last_triggered if k[0] >= today}
                        
                        log.info(f"[CollectMoney] Kich hoat scheduler cho khung gio {label}")
                        task = asyncio.create_task(run_collect_money_report(label))
                        
                        def _after_run(t):
                            log_next_run(datetime.now(TZ), SCHEDULE)
                        task.add_done_callback(_after_run)
        except Exception as e:
            log.error(f"[CollectMoney] Loi loop scheduler: {e}")
            
        await asyncio.sleep(15) # Check check mỗi 15 giây để chính xác hơn
