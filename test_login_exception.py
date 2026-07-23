import sys
sys.path.insert(0, r"C:\Users\Admin\.gemini\antigravity-ide\scratch\ghn_dashboard")
import main
import asyncio

async def test():
    class DummyRequest:
        client = None
        async def json(self):
            return {"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"}

    try:
        res = await main.login(DummyRequest(), {"username": "giaohangnangmientrung", "password": "GXT@MienTrung2026!"})
        print("LOGIN RESULT:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
