#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_money_bot.py
====================
Bot giả lập thao tác trên trình duyệt Chrome (qua CDP port 9222)
để kiểm tra tình trạng "Thu tiền - Bắn kiểm" theo từng kho và báo cáo qua Telegram.
"""

import asyncio
import html
import sys
import io
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from playwright.async_api import async_playwright

# Setup encoding for windows stdout / log output (Windows-only to avoid Railway crash)
if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Configure logging
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "collect_money_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("collect_money_bot")

def load_env():
    # Try finding .env file in the current directory and up to 3 levels up
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            log.info(f"Loaded environment variables from: {env_path}")
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
        current_dir = os.path.dirname(current_dir)

# Load environment variables
load_env()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("WARN_CHAT_ID", "")
TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TIMEZONE_STR)
GHN_COLLECT_URL = os.environ.get(
    "GHN_COLLECT_URL",
    "https://nhanh.ghn.vn/lastmile/receipt/collect-money-management"
)
CDP_URL = "http://127.0.0.1:9222"

def parse_int(val_str: str) -> int:
    try:
        # Trích xuất các số từ chuỗi
        cleaned = "".join([c for c in val_str if c.isdigit()])
        return int(cleaned) if cleaned else 0
    except Exception:
        return 0

async def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID trong env.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            text = text[:3900] + "\n\n<i>[Báo cáo bị cắt bớt do quá dài...]</i>"
            
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            })
            
        if resp.status_code == 200:
            log.info("Gui Telegram thanh cong.")
            return True
            
        # Log chi tiết lỗi Telegram
        err_data = resp.json()
        description = err_data.get("description", "")
        error_code = err_data.get("error_code")
        
        if error_code == 401 or "Unauthorized" in description:
            log.error(f"[TELEGRAM ERROR] Sai TELEGRAM_BOT_TOKEN hoac Token khong hop le. Chi tiet: {description}")
        elif error_code == 400 and "chat not found" in description:
            log.error(f"[TELEGRAM ERROR] Sai TELEGRAM_CHAT_ID (chat not found). Vui long kiem tra lai Chat ID: {TELEGRAM_CHAT_ID}")
        elif error_code == 403 or "forbidden" in description.lower():
            log.error(f"[TELEGRAM ERROR] Bot chua duoc add vao group hoac khong co quyen gui tin nhan. Chi tiet: {description}")
        else:
            log.error(f"[TELEGRAM ERROR] Gui tin nhan Telegram that bai (status={resp.status_code}, error_code={error_code}): {description}")
        return False
    except Exception as e:
        log.error(f"Loi gui tin nhan Telegram: {e}")
        return False

async def send_report(warehouse_names, report_data, error_warehouses) -> bool:
    now_str = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    
    if not report_data:
        # Khong co ton
        msg = (
            f"🚨 <b>BÁO CÁO THU TIỀN - BẮN KIỂM</b>\n"
            f"Thời gian: {now_str}\n\n"
            f"Không có đơn chưa thu tiền/chưa bắn kiểm."
        )
    else:
        # Tinh toan cac so lieu tong quan
        total_wh_checked = len(warehouse_names)
        total_wh_issues = len(report_data)
        total_emp_issues = sum(len(wh["issues"]) for wh in report_data)
        total_dh_thu_tien = sum(sum(emp["dh_thu_tien"] for emp in wh["issues"]) for wh in report_data)
        total_dh_luu_kho = sum(sum(emp["dh_luu_kho"] for emp in wh["issues"]) for wh in report_data)
        total_dh_ban_kiem = sum(sum(emp["dh_ban_kiem"] for emp in wh["issues"]) for wh in report_data)
        
        # Format theo yeu cau o muc 7 mới
        msg = (
            f"🚨 <b>BÁO CÁO THU TIỀN - BẮN KIỂM</b>\n"
            f"Thời gian: {now_str}\n\n"
            f"<b>Tổng quan:</b>\n"
            f"- Tổng kho đã kiểm tra: {total_wh_checked}\n"
            f"- Kho còn tồn: {total_wh_issues}\n"
            f"- Tổng nhân viên còn tồn: {total_emp_issues}\n"
            f"- Tổng ĐH cần thu tiền: {total_dh_thu_tien}\n"
            f"- Tổng ĐH cần lưu kho: {total_dh_luu_kho}\n"
            f"- Tổng ĐH cần bắn kiểm: {total_dh_ban_kiem}\n\n"
            f"<b>Chi tiết theo kho:</b>\n\n"
        )
        
        for idx, wh in enumerate(report_data, 1):
            msg += f"{idx}. <b>{wh['wh_name']}</b>\n"
            for emp in wh["issues"]:
                emp_label = f"{emp['emp_code']} - {emp['emp_name']}" if emp['emp_code'] else emp['emp_name']
                msg += f"• <b>{emp_label}</b>\n"
                if emp['dh_thu_tien'] > 0:
                    msg += f"  - ĐH cần thu tiền: {emp['dh_thu_tien']}\n"
                    tct = emp['tien_can_thu'].strip()
                    if tct and tct != "0" and tct != "0đ":
                        msg += f"  - Tiền cần thu: {tct}\n"
                if emp['dh_luu_kho'] > 0:
                    msg += f"  - ĐH cần lưu kho: {emp['dh_luu_kho']}\n"
                if emp['dh_ban_kiem'] > 0:
                    msg += f"  - ĐH cần bắn kiểm: {emp['dh_ban_kiem']}\n"
                if emp['deadline']:
                    msg += f"  - Hoàn thành trước: {emp['deadline']}\n"
            msg += "\n"
            
        msg += "Yêu cầu các kho kiểm tra và hoàn tất thu tiền/bắn kiểm đúng hạn."
        
    if error_warehouses:
        msg += "\n\n⚠️ <b>Lỗi xảy ra:</b>"
        for err_wh in error_warehouses:
            msg += f"\n- Không đọc được dữ liệu kho {err_wh}, cần kiểm tra lại."
            
    # Gui tin nhan
    return await send_telegram_message(msg)

async def run_collect_money_check() -> bool:
    start_time_str = datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")
    log.info("=== BAT DAU KIEM TRA THU TIEN - BAN KIEM ===")
    
    using_cdp = False
    browser = None
    page = None
    
    try:
        async with async_playwright() as p:
            try:
                log.info(f"Dang ket noi Chrome CDP qua: {CDP_URL}...")
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                log.info("Ket noi Chrome CDP thanh cong.")
                using_cdp = True
                
                context = browser.contexts[0]
                for p_obj in context.pages:
                    if "nhanh.ghn.vn/lastmile/receipt/collect-money-management" in p_obj.url:
                        page = p_obj
                        log.info("Tim thay tab nhanh.ghn.vn dang mo tren Chrome CDP.")
                        break
                if not page:
                    page = await context.new_page()
                    log.info("Khong tim thay tab nhanh.ghn.vn, da mo tab moi tren Chrome CDP.")
            except Exception as cdp_err:
                # Nếu không kết nối được Chrome debug (Yêu cầu 5)
                err_msg = "BOT không kết nối được Chrome debug. Vui lòng mở file start_chrome_debug và kiểm tra trang GHN đã đăng nhập."
                log.error(f"{err_msg}. Chi tiet: {cdp_err}")
                await send_telegram_message(err_msg)
                return False

            # Load trang GHN (thử tối đa 3 lần)
            load_success = False
            for attempt in range(1, 4):
                try:
                    log.info(f"Mo trang kiem tra (Lan {attempt}/3): {GHN_COLLECT_URL}")
                    await page.goto(GHN_COLLECT_URL, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                    load_success = True
                    break
                except Exception as goto_err:
                    log.warning(f"Loi load trang lan {attempt}: {goto_err}")
                    if attempt < 3:
                        log.info("Cho 5 giay va reload lai trang...")
                        await asyncio.sleep(5)
            
            if not load_success:
                log.error("Khong the load trang GHN sau 3 lan thu.")
                await send_telegram_message("❌ <b>Bot không thể mở trang GHN do kết nối mạng hoặc trang load quá chậm.</b>")
                if using_cdp and browser:
                    await browser.close()
                return False
            
            current_url = page.url
            log.info(f"Page URL hien tai: {current_url}")
            
            # Kiem tra phien dang nhap (Yêu cầu 6)
            is_login_page = "login" in current_url.lower() or await page.locator("input[type='password']").is_visible(timeout=2000)
            if is_login_page:
                log.warning("Phien dang nhap GHN da het han, can dang nhap lai.")
                await send_telegram_message("Phiên đăng nhập GHN đã hết hạn. Vui lòng đăng nhập lại trên Chrome debug.")
                if using_cdp and browser:
                    await browser.close()
                return False

            # Dropdown load loop - Thử reload lại trang tối đa 3 lần nếu không tải được dropdown hoặc dropdown trống
            dropdown_success = False
            warehouse_names = []
            
            for dropdown_attempt in range(1, 4):
                log.info(f"Kiem tra / Tai danh sach kho (Lan thu {dropdown_attempt}/3)...")
                
                # Chờ ô chọn kho hiển thị
                select_locator = page.locator(".ant-select-selector").first
                try:
                    await select_locator.wait_for(state="visible", timeout=10000)
                    log.info("Tim thay o chon kho.")
                except Exception as e:
                    log.warning(f"Khong tim thay o chon kho tai lan thu {dropdown_attempt}: {e}")
                    log.info("Refresh trang va thu lai...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(4000)
                    continue

                # Click mở dropdown
                await select_locator.click()
                await page.wait_for_timeout(1500)
                
                # Đọc danh sách kho
                seen_warehouses = set()
                warehouse_names = []
                holder_locator = page.locator(".rc-virtual-list-holder").first
                try:
                    await holder_locator.wait_for(state="visible", timeout=5000)
                    await holder_locator.evaluate("el => el.scrollTop = 0")
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

                # Cuộn ảo để đọc hết
                last_len = -1
                no_new_count = 0
                max_scrolls = 150
                
                for scroll_idx in range(max_scrolls):
                    options_locator = page.locator(".ant-select-dropdown .ant-select-item-option")
                    opt_count = await options_locator.count()
                    
                    if opt_count == 0:
                        options_locator = page.locator(".ant-select-item-option-content")
                        opt_count = await options_locator.count()
                    
                    for i in range(opt_count):
                        text = await options_locator.nth(i).inner_text()
                        text_strip = text.strip()
                        if text_strip and text_strip not in seen_warehouses:
                            seen_warehouses.add(text_strip)
                            warehouse_names.append(text_strip)
                    
                    if len(seen_warehouses) == last_len:
                        no_new_count += 1
                        if no_new_count >= 8:
                            break
                    else:
                        no_new_count = 0
                        last_len = len(seen_warehouses)
                    
                    if await holder_locator.count() > 0:
                        await holder_locator.evaluate("el => el.scrollTop += 250")
                        await page.wait_for_timeout(200)
                    else:
                        break
                
                # Click lại đóng dropdown
                await select_locator.click()
                await page.wait_for_timeout(500)
                
                if len(warehouse_names) > 0:
                    dropdown_success = True
                    break
                else:
                    log.warning(f"Danh sach kho trong dropdown rỗng ở lần thử {dropdown_attempt}. Refresh trang và thử lại...")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(4000)
            
            total_dropdown_found = len(warehouse_names)
            log.info(f"Tong cong da tim thay {total_dropdown_found} kho trong dropdown.")
            
            if not dropdown_success or total_dropdown_found == 0:
                log.error("[ERR_DOM] Khong doc duoc danh sach kho tu dropdown Virtual List sau 3 lan thu.")
                await send_telegram_message("❌ <b>Bot không thể đọc danh sách kho từ dropdown GHN.</b>")
                if using_cdp and browser:
                    await browser.close()
                return False
            
            report_data = []
            error_warehouses = []
            
            # Khởi tạo lại ô chọn kho locator
            select_locator = page.locator(".ant-select-selector").first
            
            for index, wh_name in enumerate(warehouse_names):
                log.info(f"[{index+1}/{total_dropdown_found}] Dang kiem tra kho: {wh_name}")
                
                try:
                    # 1. Click vao select container de mo dropdown
                    await select_locator.click()
                    await page.wait_for_timeout(500)
                    
                    # 2. Nhap ma kho de loc
                    wh_code = wh_name.split(" - ")[0].strip()
                    search_input = page.locator("input.ant-select-selection-search-input").first
                    await search_input.evaluate("el => el.focus()")
                    await search_input.fill(wh_code)
                    await page.wait_for_timeout(800)
                    
                    # 3. Click chon ket qua dau tien
                    first_option = page.locator(".ant-select-dropdown .ant-select-item-option").first
                    await first_option.click()
                    log.info(f"Da chon kho qua search: {wh_name}")
                except Exception as e:
                    log.error(f"Khong the chon kho {wh_name} qua search: {e}")
                    error_warehouses.append(wh_name)
                    debug_path = os.path.join(LOG_DIR, f"debug_err_{index}.png")
                    await page.screenshot(path=debug_path)
                    try:
                        await select_locator.click()
                    except:
                        pass
                    continue
                
                # Cho load
                await page.wait_for_timeout(2500)
                
                # Cho spinner
                try:
                    spinner = page.locator(".ant-spin-spinning").first
                    if await spinner.is_visible(timeout=1000):
                        await spinner.wait_for(state="hidden", timeout=12000)
                        await page.wait_for_timeout(500)
                except Exception:
                    pass
                
                # Kiem tra empty
                is_empty = False
                try:
                    empty_el = page.locator(".ant-empty").first
                    if await empty_el.is_visible(timeout=1000):
                        is_empty = True
                        log.info(f"Kho {wh_name} khong co du lieu (Empty).")
                except Exception:
                    pass
                
                if is_empty:
                    continue
                
                # Lay dong du lieu
                rows_locator = page.locator(".ant-table-tbody tr.ant-table-row")
                rows_count = await rows_locator.count()
                
                if rows_count == 0:
                    await page.wait_for_timeout(2000)
                    rows_count = await rows_locator.count()
                    if rows_count == 0:
                        log.info(f"Kho {wh_name} load ra bang trong.")
                        continue
                
                warehouse_issues = []
                for r_idx in range(rows_count):
                    row = rows_locator.nth(r_idx)
                    cells = row.locator("td")
                    cells_count = await cells.count()
                    
                    if cells_count < 7:
                        continue
                    
                    crep_text = await cells.nth(0).inner_text()
                    crep_lines = [line.strip() for line in crep_text.split("\n") if line.strip()]
                    
                    emp_code = ""
                    emp_name = ""
                    if len(crep_lines) >= 2:
                        emp_code = crep_lines[0]
                        emp_name = crep_lines[1]
                    elif len(crep_lines) == 1:
                        if crep_lines[0].isdigit():
                            emp_code = crep_lines[0]
                        else:
                            emp_name = crep_lines[0]
                    
                    if not emp_code and not emp_name:
                        continue
                        
                    name_lower = emp_name.lower()
                    code_lower = emp_code.lower()
                    if "tổng" in name_lower or "tổng" in code_lower or "cộng" in name_lower or "cộng" in code_lower:
                        continue
                            
                    partner = (await cells.nth(1).inner_text()).strip()
                    dh_thu_tien_str = (await cells.nth(2).inner_text()).strip()
                    dh_thu_tien = parse_int(dh_thu_tien_str)
                    tien_can_thu_str = (await cells.nth(3).inner_text()).strip()
                    dh_luu_kho_str = (await cells.nth(4).inner_text()).strip()
                    dh_luu_kho = parse_int(dh_luu_kho_str)
                    dh_ban_kiem_str = (await cells.nth(5).inner_text()).strip()
                    dh_ban_kiem = parse_int(dh_ban_kiem_str)
                    deadline = (await cells.nth(6).inner_text()).strip()
                    
                    # Dieu kien bao cao (Yêu cầu 3)
                    if dh_thu_tien > 0 or dh_ban_kiem > 0 or dh_luu_kho > 0:
                        warehouse_issues.append({
                            "emp_code": emp_code,
                            "emp_name": emp_name,
                            "partner": partner,
                            "dh_thu_tien": dh_thu_tien,
                            "tien_can_thu": tien_can_thu_str,
                            "dh_luu_kho": dh_luu_kho,
                            "dh_ban_kiem": dh_ban_kiem,
                            "deadline": deadline
                        })
                        
                if warehouse_issues:
                    report_data.append({
                        "wh_name": wh_name,
                        "issues": warehouse_issues
                    })
            
            # Gui bao cao den Telegram
            telegram_success = await send_report(warehouse_names, report_data, error_warehouses)
            
            # Tính toán các số liệu thống kê bắt buộc để ghi log (Yêu cầu 7)
            total_wh_checked = total_dropdown_found - len(error_warehouses)
            total_wh_issues = len(report_data)
            total_dh_thu_tien = sum(sum(emp["dh_thu_tien"] for emp in wh["issues"]) for wh in report_data)
            total_dh_luu_kho = sum(sum(emp["dh_luu_kho"] for emp in wh["issues"]) for wh in report_data)
            total_dh_ban_kiem = sum(sum(emp["dh_ban_kiem"] for emp in wh["issues"]) for wh in report_data)

            log.info("=== THONG KE CHAY BOT ===")
            log.info(f"Thời gian bắt đầu check: {start_time_str}")
            log.info(f"Tổng số kho tìm thấy trong dropdown: {total_dropdown_found}")
            log.info(f"Số kho đã kiểm tra: {total_wh_checked}")
            log.info(f"Số kho còn tồn: {total_wh_issues}")
            log.info(f"Tổng đơn cần thu tiền: {total_dh_thu_tien}")
            log.info(f"Tổng đơn cần lưu kho: {total_dh_luu_kho}")
            log.info(f"Tổng đơn cần bắn kiểm: {total_dh_ban_kiem}")
            log.info(f"Telegram gửi thành công hay thất bại: {'Thành công' if telegram_success else 'Thất bại'}")
            if error_warehouses:
                log.info(f"Lỗi chi tiết (Danh sách kho gặp sự cố): {error_warehouses}")
            log.info("=== HOAN THANH BOT THU TIEN - BAN KIEM ===")
            
            if using_cdp and browser:
                await browser.close()
            return True
            
    except Exception as e:
        log.exception(f"Loi nghiem trong luc chay bot: {e}")
        if using_cdp and browser:
            try:
                await browser.close()
            except:
                pass
        await send_telegram_message(f"❌ <b>Bot kiểm tra xảy ra lỗi hệ thống:</b> <code>{html.escape(str(e)[:300])}</code>")
        return False

if __name__ == "__main__":
    asyncio.run(run_collect_money_check())
