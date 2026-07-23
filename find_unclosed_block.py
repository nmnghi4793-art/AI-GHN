import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Test line by line cumulative to find exact line where V8 throws Unexpected end of input or SyntaxError
        chunk = ""
        for i, line in enumerate(lines):
            chunk += line
            # Every 100 lines or at function boundary test syntax
            if (i + 1) % 50 == 0 or i == len(lines) - 1:
                try:
                    # Append enough closing braces to see if it parses
                    test_str = chunk
                    # Balance curlies temporarily
                    open_c = test_str.count('{') - test_str.count('}')
                    if open_c > 0:
                        test_str += "\n}" * open_c
                    page.evaluate(f"() => {{ {test_str} }}")
                except Exception as e:
                    err_msg = str(e)
                    if "Unexpected end of input" not in err_msg and "Missing" not in err_msg:
                        print(f"SYNTAX ERROR AT LINE {i+1}: {err_msg}")
                        print(f"Line content: {line.strip()}")

        browser.close()

if __name__ == "__main__":
    run()
