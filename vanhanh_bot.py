#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vanhanh_bot.py
==============
Bot giả lập trình duyệt Playwright để kiểm tra phiếu tồn vận hành bưu cục
và báo cáo qua Telegram.
"""

import os
import re
import json
import asyncio
import logging
import sys
import io
import html
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from playwright.async_api import async_playwright

# Configure logging
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "vanhanh_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("vanhanh_bot")

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

VANHANH_URL = os.environ.get("VANHANH_URL", "https://ghn-vanhanh.dedyn.io/")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("WARN_CHAT_ID", "")
TIMEZONE_STR = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TIMEZONE_STR)

STATE_FILE = os.path.join(LOG_DIR, "vanhanh_state.json")

# Danh sách 25 bưu cục cần giám sát
TARGET_CODES = {
    "22782000", "22168000", "22059000", "22057000", "22028000",
    "21682000", "21525000", "21521000", "21498000", "21483000",
    "21386000", "21347000", "21285000", "21284000", "21283000",
    "21163000", "21162000", "21096000", "21095000", "21094000",
    "21091000", "21090000", "21089000", "21087000", "21086000"
}

# Ánh xạ tên bưu cục đầy đủ từ mã
WAREHOUSE_NAMES = {
    "22782000": "Kho Giao Hàng Nặng - Buôn Hồ - Đắk Lắk",
    "22168000": "Kho Giao Hàng Nặng - Hoài Nhơn - Bình Định",
    "22059000": "Kho Giao Hàng Nặng - Hoà Xuân - Đà Nẵng",
    "22057000": "Kho Giao Hàng Nặng - Tuy Phong - Bình Thuận",
    "22028000": "Kho Giao Hàng Nặng - La Gi - Bình Thuận",
    "21682000": "Kho Giao Hàng Nặng - Thạch Linh - Hà Tĩnh",
    "21525000": "Kho Giao Hàng Nặng - Gia Nghĩa - Đắk Nông",
    "21521000": "Kho Giao Hàng Nặng - Đông Hà - Quảng Trị",
    "21498000": "Kho Giao Hàng Nặng - Cam Ranh - Khánh Hoà",
    "21483000": "Kho Giao Hàng Nặng - Tam Kỳ - Quảng Nam",
    "21386000": "Kho Giao Hàng Nặng - Hội An - Quảng Nam",
    "21347000": "Kho Giao Hàng Nặng - Tuy Hoà - Phú Yên",
    "21285000": "Kho Giao Hàng Nặng - Phan Thiết - Bình Thuận",
    "21284000": "Kho Giao Hàng Nặng - Quảng Ngãi - Quảng Ngãi",
    "21283000": "Kho Giao Hàng Nặng - Đồng Hới - Quảng Bình",
    "21163000": "Kho Giao Hàng Nặng - Phan Rang - Ninh Thuận",
    "21162000": "Kho Giao Hàng Nặng - Thắng Lợi - Kon Tum",
    "21096000": "Kho Giao Hàng Nặng - Hương Thủy - Huế",
    "21095000": "Kho Giao Hàng Nặng - Vinh - Nghệ An",
    "21094000": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hoà",
    "21091000": "Kho Giao Hàng Nặng - Pleiku - Gia Lai",
    "21090000": "Kho Giao Hàng Nặng - Buôn Ma Thuột - Đắk Lắk",
    "21089000": "Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng",
    "21087000": "Kho Giao Hàng Nặng - Quy Nhơn - Bình Định",
    "21086000": "Kho Giao Hàng Nặng - Đông Thọ - Thanh Hoá"
}

def parse_int(val_str: str) -> int:
    try:
        cleaned = "".join([c for c in val_str if c.isdigit()])
        return int(cleaned) if cleaned else 0
    except Exception:
        return 0

async def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID")
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
            log.info("Gui Telegram van hanh thanh cong.")
            return True
        log.error(f"Gui Telegram that bai (status={resp.status_code}): {resp.text}")
        return False
    except Exception as e:
        log.error(f"Loi gui tin nhan Telegram: {e}")
        return False

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "active_tickets" not in data:
                    data["active_tickets"] = {}
                if "last_summary_sent" not in data:
                    data["last_summary_sent"] = ""
                # Chuẩn hóa trạng thái của các phiếu cũ để có cờ notified
                for ticket in data["active_tickets"].values():
                    if "notified" not in ticket:
                        ticket["notified"] = True
                return data
        except Exception as e:
            log.error(f"Loi doc file state: {e}")
    return {"active_tickets": {}, "last_summary_sent": ""}

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Loi ghi file state: {e}")

async def run_vanhanh_check() -> bool:
    log.info("=== BAT DAU KIEM TRA TON PHIEU VAN HANH GXT ===")
    
    state = load_state()
    active_tickets = state.get("active_tickets", {})

    now_str = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    
    browser = None
    context = None
    page = None
    using_cdp = False
    is_tab_already_open = False
    is_local = not os.environ.get("RAILWAY_ENVIRONMENT")
    
    try:
        async with async_playwright() as p:
            if is_local:
                try:
                    log.info("Dang ket noi Chrome CDP...")
                    browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    log.info("Ket noi Chrome CDP thanh cong.")
                    using_cdp = True
                    
                    context = browser.contexts[0]
                    for p_obj in context.pages:
                        if "ghn-vanhanh.dedyn.io" in p_obj.url or "baocao.ghn.vn" in p_obj.url:
                            page = p_obj
                            log.info("Tim thay tab van hanh dang mo tren Chrome CDP.")
                            break
                            
                    is_tab_already_open = page is not None
                    if not page:
                        page = await context.new_page()
                        log.info("Khong tim thay tab van hanh, da mo tab moi tren Chrome CDP.")
                        await page.goto(VANHANH_URL, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2000)
                except Exception as cdp_err:
                    log.warning("Chưa mở Chrome debug. Vui lòng chạy file start_chrome_debug.")
                    return False
            else:
                log.info("Dang khoi chay browser headless tren Railway...")
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                log.info(f"Truy cap trang: {VANHANH_URL}")
                await page.goto(VANHANH_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

            # Kiem tra neu dang o trang dang nhap
            current_url = page.url
            is_login_page = "login" in current_url.lower() or await page.locator("input[type='password']").is_visible(timeout=2000)
            
            if is_login_page:
                if is_local:
                    log.warning("Phien dang nhap GHN da het han hoac chua dang nhap tren Chrome local.")
                    warning_text = (
                        "⚠️ BOT VẬN HÀNH KHÔNG HOẠT ĐỘNG\n"
                        "Lý do: Phiên đăng nhập GHN Vận hành đã hết hạn hoặc chưa đăng nhập.\n"
                        "Vui lòng đăng nhập lại trên Chrome debug local."
                    )
                    await send_telegram_message(warning_text)
                    if page and not is_tab_already_open:
                        await page.close()
                    return False
                else:
                    log.info("Dang thuc hien dang nhap tu dong tren Railway...")
                    username = os.environ.get("VANHANH_USERNAME")
                    password = os.environ.get("VANHANH_PASSWORD")
                    if not username or not password:
                        log.error("Thieu bien moi truong VANHANH_USERNAME hoac VANHANH_PASSWORD tren Railway.")
                        await send_telegram_message(
                            "❌ <b>Bot vận hành lỗi trên Railway:</b> Thiếu tài khoản đăng nhập (VANHANH_USERNAME/VANHANH_PASSWORD)."
                        )
                        if browser:
                            await browser.close()
                        return False
                        
                    # Dien thong tin dang nhap
                    username_input = page.locator('label:has-text("Tài khoản") input, input[type="text"]').first
                    await username_input.fill(username)
                    
                    password_input = page.locator('label:has-text("Mật khẩu") input, input[type="password"]').first
                    await password_input.fill(password)
                    
                    # Click Dang nhap
                    login_btn = page.locator('button:has-text("Đăng nhập"), button[type="submit"], button').first
                    await login_btn.click()
                    await page.wait_for_timeout(3000)
                    
                    # Kiem tra ket qua dang nhap
                    current_url = page.url
                    if "login" in current_url.lower():
                        log.error("Dang nhap that bai. Van o lai trang login.")
                        await send_telegram_message(
                            "❌ <b>Bot vận hành lỗi trên Railway:</b> Đăng nhập tài khoản thất bại (sai username/password hoặc lỗi hệ thống)."
                        )
                        if browser:
                            await browser.close()
                        return False
                    log.info("Dang nhap tu dong thanh cong.")

            # Chờ trang bưu cục load ra
            loaded = False
            for attempt in range(1, 4):
                try:
                    await page.locator("input#bcSearch").wait_for(state="visible", timeout=8000)
                    await page.locator(".bc-item").first.wait_for(state="visible", timeout=5000)
                    loaded = True
                    break
                except Exception:
                    log.warning(f"Lan thu {attempt} load danh sach kho that bai. Dang tai lai trang...")
                    await page.goto(VANHANH_URL, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

            if not loaded:
                log.error("Khong load duoc danh sach kho sau 3 lan thu.")
                await send_telegram_message("❌ <b>Bot không load được danh sách kho, cần kiểm tra website.</b>")
                if not using_cdp:
                    await browser.close()
                else:
                    if page and not is_tab_already_open:
                        await page.close()
                return False

            # Bỏ chọn tất cả bưu cục cũ để chuẩn bị chọn bưu cục mục tiêu
            log.info("Bo chon tat ca buu cuc hien tai...")
            try:
                await page.locator("button#clearSel").click()
                await page.wait_for_timeout(500)
            except Exception as e:
                log.warning(f"Khong click duoc nut bo chon tat ca: {e}")

            # Lọc và chọn bưu cục giao hàng nặng
            log.info("Loc va tick chon 25 buu cuc giao hang nang...")
            await page.locator("input#bcSearch").fill("giao hang nang")
            await page.wait_for_timeout(1000)

            items = page.locator(".bc-item")
            item_count = await items.count()
            selected_count = 0

            for i in range(item_count):
                item = items.nth(i)
                text = await item.inner_text()
                # Trích xuất mã bưu cục (8 chữ số đầu tiên)
                m = re.match(r'^(\d{8})', text.strip())
                if m:
                    code = m.group(1)
                    if code in TARGET_CODES:
                        checkbox = item.locator('input[type="checkbox"]')
                        if not await checkbox.is_checked():
                            await checkbox.click()
                            await page.wait_for_timeout(50)
                        selected_count += 1

            log.info(f"Da chon {selected_count}/25 kho trong phan loc batch.")

            # Fallback check: Nếu số lượng được chọn chưa đủ 25, lọc tìm riêng từng mã
            if selected_count < 25:
                log.info("So buu cuc da chon chua du 25. Chay fallback tim kiem rieng tung ma...")
                for code in TARGET_CODES:
                    await page.locator("input#bcSearch").fill(code)
                    await page.wait_for_timeout(300)
                    item = page.locator(".bc-item").first
                    if await item.count() > 0:
                        text = await item.inner_text()
                        if code in text:
                            checkbox = item.locator('input[type="checkbox"]')
                            if not await checkbox.is_checked():
                                await checkbox.click()
                                await page.wait_for_timeout(50)

            # Nhấn xem dữ liệu
            log.info("Nhan Xem du lieu...")
            await page.locator("button#viewBtn, button.btn-primary").first.click()
            await page.wait_for_timeout(2500)

            # Chờ bảng dữ liệu hiện ra
            await page.locator("table").first.wait_for(state="visible", timeout=10000)
            
            rows = page.locator("table tbody tr")
            row_count = await rows.count()
            log.info(f"Tìm thay {row_count} dong trong bang du lieu.")

            scraped_keys = set()

            for r_idx in range(row_count):
                row = rows.nth(r_idx)
                cells = row.locator("td")
                if await cells.count() < 5:
                    continue
                
                wh_name = (await cells.nth(0).inner_text()).strip()
                if not wh_name or "tổng" in wh_name.lower():
                    continue

                total_str = (await cells.nth(4).inner_text()).strip()
                total = parse_int(total_str)
                
                if total == 0:
                    continue

                log.info(f"Buu cuc {wh_name} co {total} phieu ton.")

                # Quét 3 cột Hồi giao, Hồi lấy, Hồi trả
                for col_idx, col_type in [(1, "Hồi giao"), (2, "Hồi lấy"), (3, "Hồi trả")]:
                    cell = cells.nth(col_idx)
                    cell_val = (await cell.inner_text()).strip()
                    cnt = parse_int(cell_val)
                    
                    if cnt > 0:
                        # Click mở popup chi tiết
                        link = cell.locator("a")
                        if await link.count() > 0:
                            await link.click()
                        else:
                            await cell.click()
                            
                        # Đợi popup hiển thị
                        await page.locator("button#modalClose, .modal-close").first.wait_for(state="visible", timeout=5000)
                        await page.wait_for_timeout(300)

                        # Đọc danh sách phiếu tồn
                        ticket_nums = page.locator(".modal-body a.ticket-num, .modal-content a.ticket-num")
                        ticket_count = await ticket_nums.count()
                        
                        for t_idx in range(ticket_count):
                            t_el = ticket_nums.nth(t_idx)
                            # Lấy phần tử cha bao bọc để lấy đầy đủ dòng chữ
                            parent_text = await t_el.evaluate("el => el.parentElement.innerText")
                            line_text = parent_text.strip()
                            line_text = re.sub(r'\s+', ' ', line_text) # Làm sạch khoảng trắng thừa
                            
                            # Trích xuất mã phiếu/Order code (VD: #691000047773)
                            m_ticket = re.search(r'#(\d+)', line_text)
                            ticket_code_raw = m_ticket.group(0) if m_ticket else ""
                            ticket_id_only = m_ticket.group(1) if m_ticket else line_text
                            
                            # Lấy href link của mã phiếu
                            href = await t_el.get_attribute("href")
                            
                            # Tách phần còn lại của dòng chữ sau mã phiếu
                            rest_text = line_text
                            if ticket_code_raw and line_text.startswith(ticket_code_raw):
                                rest_text = line_text[len(ticket_code_raw):].strip()
                            elif ticket_id_only and line_text.startswith(ticket_id_only):
                                rest_text = line_text[len(ticket_id_only):].strip()
                            
                            escaped_code = html.escape(ticket_code_raw if ticket_code_raw else ticket_id_only)
                            escaped_rest = html.escape(rest_text)
                            
                            formatted_line = f"{escaped_code} {escaped_rest}"
                            if href:
                                # Resolve relative link
                                if not href.startswith("http://") and not href.startswith("https://"):
                                    base_url = VANHANH_URL.rstrip('/')
                                    if not href.startswith("/"):
                                        href = "/" + href
                                    full_link = f"{base_url}{href}"
                                else:
                                    full_link = href
                                formatted_line = f'<a href="{full_link}">{escaped_code}</a> {escaped_rest}'
                            
                            key = f"{wh_name}_{col_type}_{ticket_id_only}"
                            scraped_keys.add(key)

                            if key in active_tickets:
                                # Phiếu đã tồn tại từ trước -> Cập nhật thời gian kiểm tra
                                active_tickets[key]["last_checked"] = now_str
                                active_tickets[key]["detail"] = formatted_line
                            else:
                                # Phiếu mới phát sinh -> Mặc định notified = False
                                active_tickets[key] = {
                                    "warehouse": wh_name,
                                    "ticket_type": col_type,
                                    "detail": formatted_line,
                                    "first_detected": now_str,
                                    "last_checked": now_str,
                                    "notified": False
                                }

                        # Click đóng popup
                        await page.locator("button#modalClose, .modal-close").first.click()
                        # Đợi popup biến mất
                        await page.locator("button#modalClose, .modal-close").first.wait_for(state="hidden", timeout=5000)
                        await page.wait_for_timeout(300)

            # Xử lý các phiếu đã biến mất (được xử lý thành công)
            resolved_keys = [k for k in active_tickets if k not in scraped_keys]
            for r_key in resolved_keys:
                del active_tickets[r_key]

            # Lưu lại trạng thái mới nhất
            state["active_tickets"] = active_tickets
            save_state(state)

            log.info(f"Quet xong. So phieu ton hien tai: {len(active_tickets)}")

            # --- PHÂN PHỐI GỬI TELEGRAM THEO KHUNG GIỜ ---
            # Chỉ gửi tin nhắn từ 07:00 đến 22:00
            now_dt = datetime.now(TZ)
            is_allowed_hours = (7 <= now_dt.hour < 22)
            log.info(f"Khung gio hien tai: {now_dt.strftime('%H:%M')}. Cho phep gui Telegram: {is_allowed_hours}")

            if is_allowed_hours:
                # 1. Gửi cảnh báo phiếu mới (notified == False)
                new_tickets = {k: v for k, v in active_tickets.items() if not v.get("notified", False)}
                if new_tickets:
                    log.info(f"Phat hien {len(new_tickets)} phieu moi. Gui Telegram ngay...")
                    sent = await send_new_tickets_report(new_tickets, now_str)
                    if sent:
                        # Cập nhật notified = True cho các phiếu đã báo
                        for k in new_tickets:
                            active_tickets[k]["notified"] = True
                        state["active_tickets"] = active_tickets
                        save_state(state)
                else:
                    log.info("Khong co phieu moi can bao ngay.")

                # 2. Gửi báo cáo tổng hợp 2 tiếng/lần
                last_summary_sent_str = state.get("last_summary_sent", "")
                should_send_summary = False
                if last_summary_sent_str:
                    try:
                        last_sent_dt = datetime.fromisoformat(last_summary_sent_str)
                        time_diff = (now_dt - last_sent_dt).total_seconds()
                        if time_diff >= 7200: # 120 minutes (2 hours)
                            should_send_summary = True
                    except Exception as ex:
                        log.warning(f"Loi parse last_summary_sent '{last_summary_sent_str}': {ex}")
                        should_send_summary = True
                else:
                    # Chua tung gui bao cao tong hop -> Thiet lap mốc gửi ngay
                    should_send_summary = True

                if should_send_summary:
                    if active_tickets:
                        log.info(f"Den moc 2 tieng. Gui bao cao tong hop ({len(active_tickets)} phieu ton)...")
                        await send_summary_report(active_tickets, now_str)
                    else:
                        log.info("Den moc 2 tieng nhung khong co phieu ton. Bo qua gui bao cao tong hop.")
                    
                    # Cap nhat moc thoi gian gui bao cao tong hop
                    state["last_summary_sent"] = now_dt.isoformat()
                    save_state(state)
            else:
                log.info("Ngoai khung gio 07:00 - 22:00. Khong gui bat ky tin nhan nao, giu nguyen các cờ notified=False.")

            return True

    except Exception as e:
        log.exception(f"Loi nghiem trong khi kiem tra ton phieu: {e}")
        await send_telegram_message(f"❌ <b>Bot kiểm tra xảy ra lỗi hệ thống:</b> <code>{html.escape(str(e)[:300])}</code>")
        return False
    finally:
        if browser:
            try:
                if using_cdp:
                    if page and not is_tab_already_open:
                        await page.close()
                    log.info("Da dong page mo them tren CDP.")
                else:
                    await browser.close()
                    log.info("Da dong trinh duyet headless.")
            except Exception as close_err:
                log.warning(f"Loi khi close/disconnect browser: {close_err}")

async def send_new_tickets_report(new_tickets: dict, now_str: str) -> bool:
    grouped = {}
    for ticket in new_tickets.values():
        wh = ticket["warehouse"]
        t_type = ticket["ticket_type"]
        group_key = (wh, t_type)
        if group_key not in grouped:
            grouped[group_key] = []
        grouped[group_key].append(ticket)
        
    blocks = []
    for (wh, t_type), tickets in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        detail_lines = [f"• {t['detail']}" for t in tickets]
        block = (
            f"Kho: {html.escape(wh)}\n"
            f"Loại phiếu: {html.escape(t_type)}\n"
            f"Số phiếu mới: {len(tickets)}\n\n"
            f"Chi tiết:\n"
            + "\n".join(detail_lines)
        )
        blocks.append(block)
        
    msg = (
        f"🆕 <b>PHIẾU MỚI PHÁT SINH</b>\n"
        f"Thời gian phát hiện: {now_str}\n\n"
        + "\n\n".join(blocks) + "\n\n"
        f"Yêu cầu kho kiểm tra và xử lý ngay."
    )
    return await send_telegram_message(msg)

async def send_summary_report(active_tickets: dict, now_str: str) -> bool:
    by_wh = {}
    for ticket in active_tickets.values():
        wh = ticket["warehouse"]
        if wh not in by_wh:
            by_wh[wh] = {
                "tickets": [],
                "counts": {"Hồi giao": 0, "Hồi lấy": 0, "Hồi trả": 0}
            }
        by_wh[wh]["tickets"].append(ticket)
        t_type = ticket["ticket_type"]
        if t_type in by_wh[wh]["counts"]:
            by_wh[wh]["counts"][t_type] += 1
            
    detail_blocks = []
    idx = 1
    for wh_name, info in sorted(by_wh.items()):
        counts = info["counts"]
        tickets = info["tickets"]
        
        ticket_lines = []
        for t in tickets:
            first_detected_time = t["first_detected"]
            if " " in first_detected_time:
                first_detected_time = first_detected_time.split(" ")[1]
            ticket_lines.append(f"• {t['detail']} — phát hiện từ {first_detected_time}")
            
        block = (
            f"{idx}. {html.escape(wh_name)}\n"
            f"- Hồi giao: {counts['Hồi giao']}\n"
            f"- Hồi lấy: {counts['Hồi lấy']}\n"
            f"- Hồi trả: {counts['Hồi trả']}\n\n"
            f"Phiếu tồn:\n"
            + "\n".join(ticket_lines)
        )
        detail_blocks.append(block)
        idx += 1
        
    msg = (
        f"🔁 <b>TỔNG HỢP PHIẾU TỒN CHƯA XỬ LÝ</b>\n"
        f"Thời gian: {now_str}\n\n"
        f"Tổng kho còn phiếu: {len(by_wh)}\n"
        f"Tổng phiếu tồn: {len(active_tickets)}\n\n"
        f"Chi tiết theo kho:\n"
        + "\n\n".join(detail_blocks)
    )
    return await send_telegram_message(msg)

if __name__ == "__main__":
    asyncio.run(run_vanhanh_check())
