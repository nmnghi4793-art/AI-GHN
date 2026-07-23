import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

def run():
    print("=== TESTING APP.JS SYNTAX IN CHROMIUM V8 ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Try evaluating app.js in context
        try:
            page.evaluate(f"() => {{ {js_content} }}")
            print("SUCCESS! app.js passed V8 syntax evaluation with ZERO errors!")
        except Exception as e:
            print("\nV8 SYNTAX ERROR DETECTED:")
            print(e)

        browser.close()

if __name__ == "__main__":
    run()
