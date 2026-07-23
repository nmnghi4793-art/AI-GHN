import sys
import time
import json
import os
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

artifacts_dir = r"C:\Users\Admin\.gemini\antigravity-ide\brain\fc12ac2f-f926-459e-8b54-362e3c5b61f4"
screenshot_path = os.path.join(artifacts_dir, "prod_dashboard_live.png")

console_logs = []
network_failed = []
page_errors = []

def run():
    print("=== TESTING REAL BROWSER EXECUTION ON HTTPS://AI-GHN-GXT.UP.RAILWAY.APP/ ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()

        page.on("console", lambda msg: console_logs.append(f"[{msg.type.upper()}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("response", lambda resp: network_failed.append(f"{resp.status} {resp.url}") if resp.status >= 400 else None)

        # 1. Open production URL
        print("Navigating to https://ai-ghn-gxt.up.railway.app/ ...")
        page.goto("https://ai-ghn-gxt.up.railway.app/", wait_until="networkidle")
        time.sleep(2)

        print(f"Page Title: {page.title()}")

        # 2. Check if login form is visible
        if page.is_visible("#login-username"):
            print("Login form detected. Filling credentials...")
            page.fill("#login-username", "giaohangnangmientrung")
            page.fill("#login-password", "GXT@MienTrung2026!")
            page.click("#login-submit-btn")
            time.sleep(2)

        # 3. Check if Profile form is visible
        if page.is_visible("#profile-wrapper") and page.locator("#profile-wrapper").is_visible():
            print("Profile Info form detected. Submitting profile...")
            if page.is_visible("#profile-kho"):
                page.select_option("#profile-kho", index=1)
            page.click("#profile-submit-btn")
            time.sleep(2)

        # 4. Wait for Dashboard to load
        print("Waiting for Dashboard to load...")
        time.sleep(3)

        # 5. Evaluate elementFromPoint
        top_element_center = page.evaluate("() => { const el = document.elementFromPoint(600, 400); return el ? { tagName: el.tagName, id: el.id, className: el.className } : null; }")
        top_element_sidebar = page.evaluate("() => { const el = document.elementFromPoint(100, 200); return el ? { tagName: el.tagName, id: el.id, className: el.className } : null; }")

        print(f"Top element at center (600, 400): {top_element_center}")
        print(f"Top element at sidebar (100, 200): {top_element_sidebar}")

        # 6. Test Sidebar Clicks
        print("\n--- Testing Navigation Clicks ---")
        nav_result_gtc = page.evaluate("() => { const btn = document.getElementById('nav-gtc'); if (btn) { btn.click(); return 'Clicked nav-gtc'; } return 'nav-gtc not found'; }")
        print(f"Click nav-gtc result: {nav_result_gtc}")
        time.sleep(1)

        gtc_active = page.evaluate("() => { const sec = document.getElementById('section-gtc'); return sec ? { active: sec.classList.contains('active'), display: sec.style.display } : null; }")
        print(f"Section GTC state: {gtc_active}")

        # 7. Check KPI Card values
        kpi_values = page.evaluate("""() => {
            const cards = Array.from(document.querySelectorAll('.kpi-value, .card-value, .stat-value'));
            return cards.map(c => c.textContent.trim()).slice(0, 15);
        }""")
        print(f"First 15 KPI card values: {kpi_values}")

        # 8. Check last update time text
        last_update_text = page.evaluate("() => { const el = document.getElementById('last-update-time'); return el ? el.textContent : null; }")
        print(f"Last update time text: {last_update_text}")

        # 9. Take Screenshot
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"\nScreenshot saved to: {screenshot_path}")

        # 10. Print summary of logs & errors
        print("\n=== CONSOLE LOGS ===")
        for log in console_logs:
            print(log)

        print("\n=== PAGE ERRORS ===")
        if page_errors:
            for err in page_errors:
                print(f"ERROR: {err}")
        else:
            print("NO UNCAUGHT PAGE ERRORS!")

        print("\n=== FAILED RESPONSES (>=400) ===")
        if network_failed:
            for nf in network_failed:
                print(f"FAILED: {nf}")
        else:
            print("NO FAILED NETWORK RESPONSES!")

        browser.close()

if __name__ == "__main__":
    run()
