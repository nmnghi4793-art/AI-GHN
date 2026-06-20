import asyncio
import os
import sys

# Load env variables from .env manually
def load_env():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from giao_hang_scheduler import send_telegram, pin_telegram_message

async def test():
    # Set GIAO_HANG_CHAT_ID to TELEGRAM_CHAT_ID if GIAO_HANG_CHAT_ID is not configured
    if not os.environ.get("GIAO_HANG_CHAT_ID"):
        os.environ["GIAO_HANG_CHAT_ID"] = os.environ.get("TELEGRAM_CHAT_ID", "")

    print(f"Testing GIAO_HANG_CHAT_ID={os.environ.get('GIAO_HANG_CHAT_ID')}")
    print("Sending test message...")
    msg_id = await send_telegram("🔔 <b>[TEST] Thử nghiệm chức năng PIN tin nhắn báo cáo B2B</b>\nNếu tin nhắn này được ghim thành công, quyền admin của BOT hoạt toàn bình thường.")
    print(f"Message ID: {msg_id}")
    if msg_id:
        ok = await pin_telegram_message(msg_id)
        print(f"Pin status: {ok}")
    else:
        print("Failed to send message.")

if __name__ == "__main__":
    asyncio.run(test())
