import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

def run():
    print("=== TESTING APP.JS DIRECT SCRIPT TAG IN CHROMIUM V8 ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # Build HTML without f-string corruption
        html = "<!DOCTYPE html><html><head></head><body><script>" + js_content + "</script></body></html>"
        page.set_content(html)

        print("\n=== PAGE PARSE ERRORS ===")
        if page_errors:
            for err in page_errors:
                print(f"ERROR: {err}")
        else:
            print("PERFECT! ZERO PARSE/SYNTAX ERRORS IN V8 CHROMIUM!")

        browser.close()

if __name__ == "__main__":
    run()
