import os
import asyncio
import logging
from vanhanh_bot import run_vanhanh_check

log = logging.getLogger("vanhanh_scheduler")

# Đọc tần suất chạy (mặc định 5 phút)
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "5"))

async def run_vanhanh_scheduler():
    log.info(f"[VanHanh] Scheduler khoi dong. Tan suat: {CHECK_INTERVAL_MINUTES} phut/lan")
    
    while True:
        try:
            log.info("[VanHanh] Kich hoat chu ky quet phieu ton tu dong...")
            await run_vanhanh_check()
        except Exception as e:
            log.error(f"[VanHanh] Loi loop scheduler: {e}")
            
        # Chờ thời gian cấu hình trước khi chạy lượt kế tiếp
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
