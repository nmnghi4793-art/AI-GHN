import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

total_lines = len(lines)
print(f"Total lines in app.js: {total_lines}")

def test_chunk(start, end, page):
    chunk = "".join(lines[start:end])
    try:
        page.evaluate(f"() => {{ function testScope() {{\n{chunk}\n}} }}")
        return True, None
    except Exception as e:
        return False, str(e)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Binary search for syntax error
        low = 0
        high = total_lines

        while low < high - 1:
            mid = (low + high) // 2
            print(f"Testing lines {low+1} to {mid} ...")
            ok, err = test_chunk(0, mid, page)
            if ok or "Unexpected end of input" in err:
                # Error is further down in the second half or chunk is missing closing brace
                print(f"  Lines 1 to {mid}: {err if not ok else 'OK'}")
                low = mid
            else:
                print(f"  Error found in first half (1 to {mid}): {err}")
                high = mid

        print(f"\nPotential syntax error around line {low+1}: {lines[low].strip()}")
        browser.close()

if __name__ == "__main__":
    run()
