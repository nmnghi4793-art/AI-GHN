import os
import asyncio
import sys
from telegram import Bot
import google.generativeai as genai

async def test_telegram(token):
    print("--- TESTING TELEGRAM BOT TOKEN ---")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set.")
        return False
    
    print(f"Token (first 10 chars): {token[:10]}...")
    try:
        bot = Bot(token)
        me = await bot.get_me()
        print(f"SUCCESS: Connected to bot @{me.username} (ID: {me.id}, Name: {me.first_name})")
        return True
    except Exception as e:
        print(f"ERROR: Failed to connect to Telegram API with this token. Detail: {e}")
        return False

def test_gemini(api_key):
    print("\n--- TESTING GEMINI API KEY ---")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        return False
        
    print(f"API Key (first 10 chars): {api_key[:10]}...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Simple test generation
        response = model.generate_content("Say hello.")
        print(f"SUCCESS: Gemini responded: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to call Gemini API. Detail: {e}")
        return False

async def main():
    # Load from environment first, fallback to user values if needed
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "8969802246:AAHsRIDzh5iCAKa70_qiKNqgGC-M_w1ygCU")
    gemini_key = os.environ.get("GEMINI_API_KEY", "AKfycbyuNkOLeJAsludrhGAf_Xen_Y_LwH1aMdIXJlxC8koE78PzfrJGh7OwVFKQjfp5qalarA")
    
    # We can also check if they are in any .env file
    print("Checking environment variables:")
    print(f"TELEGRAM_BOT_TOKEN in env: {'TELEGRAM_BOT_TOKEN' in os.environ}")
    print(f"GEMINI_API_KEY in env: {'GEMINI_API_KEY' in os.environ}")
    
    tg_ok = await test_telegram(token)
    gemini_ok = test_gemini(gemini_key)
    
    print("\n--- DIAGNOSTIC SUMMARY ---")
    if tg_ok and gemini_ok:
        print("Both credentials are technically valid. The issue is likely runtime startup or group privacy.")
    else:
        if not tg_ok:
            print("Telegram Bot Token is INVALID or cannot reach API.")
        if not gemini_ok:
            print("Gemini API Key is INVALID.")

if __name__ == "__main__":
    asyncio.run(main())
