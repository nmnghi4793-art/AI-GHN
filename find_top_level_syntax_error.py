import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open('app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("=== EVALUATING TOP LEVEL FUNCTIONS ONE BY ONE ===")
        # Group lines into blocks separated by blank lines or function keywords
        blocks = []
        curr_block = []
        curr_start = 1

        for idx, line in enumerate(lines):
            if (line.startswith("function ") or line.startswith("async function ") or line.startswith("// =")) and curr_block:
                blocks.append((curr_start, idx, "".join(curr_block)))
                curr_block = [line]
                curr_start = idx + 1
            else:
                curr_block.append(line)

        if curr_block:
            blocks.append((curr_start, len(lines), "".join(curr_block)))

        print(f"Total blocks identified: {len(blocks)}")
        failed_blocks = 0

        for start, end, code in blocks:
            try:
                page.evaluate(f"() => {{ {code} }}")
            except Exception as e:
                err_msg = str(e)
                if "is not defined" not in err_msg and "Cannot read" not in err_msg:
                    print(f"Block lines {start}-{end} failed: {err_msg.splitlines()[0]}")
                    print(f"Header: {lines[start-1].strip()[:80]}")
                    failed_blocks += 1

        print(f"\nFailed syntax blocks: {failed_blocks}")
        browser.close()

if __name__ == "__main__":
    run()
