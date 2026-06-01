import os
import re
import json
import base64
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Bộ nhớ đệm lưu trữ các tin nhắn thuộc cùng một Album (Media Group)
MEDIA_GROUPS = {}

# Cắt chuỗi và trích xuất dữ liệu từ caption của người dùng
def parse_caption(text: str) -> dict:
    if not text:
        return {}
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    result = {
        "id_kho": "",
        "ten_kho": "",
        "ncc": "",
        "ngay": "",
        "bien_so": ""
    }
    
    for line in lines:
        line_lower = line.lower()
        
        # 1. Dòng chứa thông tin Kho (ví dụ: "1. 21089000 - Kho Giao Hàng Nặng...")
        if "kho" in line_lower:
            m = re.search(r'(\d{5,12})\s*-\s*(.*)', line)
            if m:
                result["id_kho"] = m.group(1).strip()
                result["ten_kho"] = m.group(2).strip()
            else:
                # Cắt theo dấu gạch ngang đầu tiên làm phương án dự phòng
                parts = line.split('-', 1)
                if len(parts) == 2:
                    digits = "".join(c for c in parts[0] if c.isdigit())
                    result["id_kho"] = digits
                    result["ten_kho"] = parts[1].strip()
                else:
                    # Loại bỏ phần tiền tố số thứ tự (ví dụ: "1. ")
                    clean = re.sub(r'^\d+\.?\s*', '', line).strip()
                    result["ten_kho"] = clean
                    
        # 2. Dòng chứa nhà cung cấp (ví dụ: "2. NCC Mạnh Cường Khánh Hoà")
        elif "ncc" in line_lower:
            clean = re.sub(r'^\d+\.?\s*ncc\s*', '', line, flags=re.IGNORECASE).strip()
            clean = re.sub(r'^:\s*', '', clean).strip() # Xóa dấu hai chấm nếu có
            result["ncc"] = clean
            
        # 3. Dòng chứa ngày (ví dụ: "3. Ngày 01/06/2026")
        elif "ngày" in line_lower or "ngay" in line_lower:
            clean = re.sub(r'^\d+\.?\s*ngày\s*', '', line, flags=re.IGNORECASE).strip()
            clean = re.sub(r'^:\s*', '', clean).strip()
            result["ngay"] = clean
            
        # 4. Dòng chứa biển số xe (ví dụ: "4. Biển Số Xe : 43H00912")
        elif "biển" in line_lower or "bien" in line_lower or "số xe" in line_lower or "so xe" in line_lower:
            clean = re.sub(r'^\d+\.?\s*(biển số xe|bien so xe|biển số|bien so|biển|bien)\s*', '', line, flags=re.IGNORECASE).strip()
            clean = re.sub(r'^:\s*', '', clean).strip()
            result["bien_so"] = clean
            
    return result

# Sử dụng Google Gemini Vision để nhận diện chỉ số ODO từ các hình ảnh
async def read_odo_with_gemini(image_parts: list) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình biến môi trường GEMINI_API_KEY trên hệ thống.")
        
    genai.configure(api_key=api_key)
    
    # Tự động dò tìm model Flash khả dụng nhất trên tài khoản
    model_name = "gemini-1.5-flash"
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            available_models = await loop.run_in_executor(
                pool, 
                lambda: [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            )
        
        flash_models = [m for m in available_models if "flash" in m.lower()]
        if flash_models:
            # Sắp xếp để chọn bản mới nhất (ví dụ: gemini-2.0-flash hoặc gemini-2.5-flash)
            flash_models.sort(reverse=True)
            model_name = flash_models[0]
            print(f"[GEMINI] Tự động chọn model: {model_name}")
        else:
            if available_models:
                model_name = available_models[0]
    except Exception as e:
        print(f"[GEMINI WARNING] Không thể lấy danh sách model, sử dụng mặc định {model_name}. Lỗi: {e}")
        
    model = genai.GenerativeModel(model_name)
    
    prompt = (
        "Hãy phân tích các hình ảnh bảng đồng hồ công tơ mét này của xe ô tô và đọc số ODO đi (lúc sáng, giá trị nhỏ hơn) và số ODO về (lúc chiều, giá trị lớn hơn).\n"
        "Nếu người dùng gửi 2 ảnh khác nhau (trong album):\n"
        "  - 1 ảnh là lúc đi (giá trị ODO nhỏ hơn, thường chụp buổi sáng).\n"
        "  - 1 ảnh là lúc về (giá trị ODO lớn hơn, thường chụp buổi chiều).\n"
        "Hãy so sánh và xác định chính xác số ODO đi (odo_di) và số ODO về (odo_ve).\n"
        "Nếu chỉ có 1 ảnh duy nhất (hoặc các ảnh có cùng chỉ số ODO), hãy gán giá trị đó cho cả odo_di và odo_ve.\n"
        "Đọc kỹ phần số ODO hiển thị trên màn hình LCD (chỉ lấy phần số nguyên, bỏ chữ km và các ký tự khác).\n\n"
        "Trả về kết quả dưới định dạng JSON duy nhất như sau (KHÔNG chứa khối mã markdown ```json):\n"
        "{\n"
        "  \"odo_di\": <số_km_đi>,\n"
        "  \"odo_ve\": <số_km_về>\n"
        "}"
    )
    
    content_parts = [prompt] + image_parts
    
    # Thực hiện tác vụ gọi API đồng bộ trong ThreadPool để tránh block event loop của FastAPI
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        response = await loop.run_in_executor(
            pool, 
            lambda: model.generate_content(content_parts)
        )
        
    text_response = response.text.strip()
    
    # Làm sạch chuỗi JSON nếu Gemini trả về cả block markdown
    if text_response.startswith("```"):
        text_response = text_response.split("```")[1]
        if text_response.startswith("json"):
            text_response = text_response[4:]
    text_response = text_response.strip()
    
    try:
        return json.loads(text_response)
    except Exception as e:
        print(f"[GEMINI ERROR] Lỗi phân tích cú pháp JSON: {text_response}. Chi tiết: {e}")
        odo_di_match = re.search(r'"odo_di"\s*:\s*(\d+)', text_response)
        odo_ve_match = re.search(r'"odo_ve"\s*:\s*(\d+)', text_response)
        return {
            "odo_di": int(odo_di_match.group(1)) if odo_di_match else 0,
            "odo_ve": int(odo_ve_match.group(1)) if odo_ve_match else 0
        }

# Gửi dữ liệu và danh sách file ảnh (dạng base64) lên Google Apps Script Webhook
async def upload_to_google_sheet(webhook_url: str, metadata: dict, image_parts: list) -> dict:
    images_payload = []
    for i, part in enumerate(image_parts):
        filename = f"odo_{metadata['bien_so']}_{metadata['ngay'].replace('/', '-')}_{i+1}.jpg"
        img_base64 = base64.b64encode(part["data"]).decode('utf-8')
        images_payload.append({
            "base64": img_base64,
            "name": filename
        })
        
    payload = {
        "id_kho": metadata.get("id_kho", ""),
        "ten_kho": metadata.get("ten_kho", ""),
        "ncc": metadata.get("ncc", ""),
        "odo_di": metadata.get("odo_di", 0),
        "odo_ve": metadata.get("odo_ve", 0),
        "ngay": metadata.get("ngay", ""),
        "bien_so": metadata.get("bien_so", ""),
        "images": images_payload
    }
    
    async with httpx.AsyncClient() as client:
        # Google Apps Script có redirect (HTTP 302) nên bắt buộc phải có follow_redirects=True
        resp = await client.post(webhook_url, json=payload, follow_redirects=True, timeout=60.0)
        
    if resp.status_code == 200:
        return resp.json()
    else:
        raise RuntimeError(f"Google Webhook phản hồi lỗi {resp.status_code}: {resp.text}")

# Xử lý toàn bộ Album (Media Group) hoặc ảnh đơn sau khi đã thu thập đủ
async def process_media_group(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    group_data = MEDIA_GROUPS.pop(media_group_id, None)
    if not group_data:
        return
        
    messages = group_data["messages"]
    
    # 1. Tìm tin nhắn có caption và tổng hợp tất cả ảnh
    caption = None
    photos = []
    primary_message = messages[0]
    
    for msg in messages:
        if msg.caption:
            caption = msg.caption
            primary_message = msg
        if msg.photo:
            photos.append(msg.photo[-1])
            
    if not caption:
        # Gửi thông báo lỗi bằng tiếng Việt chuẩn
        await primary_message.reply_text(
            "❌ Vui lòng nhập nội dung mô tả kèm theo ảnh.\n\n"
            "Mẫu mô tả:\n"
            "1. 21089000 - Kho Giao Hàng Nặng Liên Chiểu - Đà Nẵng\n"
            "2. NCC Mạnh Cường Khánh Hoà\n"
            "3. Ngày 01/06/2026\n"
            "4. Biển Số Xe : 43H00912"
        )
        return
        
    status_message = await primary_message.reply_text("⏳ Đang tải ảnh và phân tích dữ liệu ODO bằng AI, vui lòng đợi trong giây lát...")
    
    try:
        # 1. Tách thông tin mô tả văn bản
        metadata = parse_caption(caption)
        
        # 2. Tải tất cả ảnh trong Album về bộ nhớ
        await status_message.edit_text(f"⏳ Đang tải {len(photos)} hình ảnh...")
        image_parts = []
        for i, photo in enumerate(photos):
            file = await photo.get_file()
            photo_bytes = await file.download_as_bytearray()
            image_parts.append({
                "mime_type": "image/jpeg",
                "data": bytes(photo_bytes)
            })
            
        # 3. Sử dụng Gemini đọc ODO từ các ảnh
        await status_message.edit_text("⏳ AI đang nhận diện chỉ số ODO từ các hình ảnh...")
        odo_results = await read_odo_with_gemini(image_parts)
        metadata["odo_di"] = odo_results.get("odo_di", 0)
        metadata["odo_ve"] = odo_results.get("odo_ve", 0)
        
        # Kiểm tra tính hợp lệ của ODO
        if metadata["odo_di"] == 0 and metadata["odo_ve"] == 0:
            raise ValueError("Không tìm thấy chỉ số ODO hợp lệ từ các ảnh. Vui lòng chụp rõ màn hình hiển thị ODO và gửi lại.")
            
        # 4. Gửi dữ liệu và ảnh đầu tiên (ảnh buổi sáng/đại diện) lên Google Sheets/Drive
        await status_message.edit_text("⏳ Đang lưu dữ liệu và lưu trữ ảnh lên Google Drive...")
        webhook_url = os.environ.get("ODO_SHEET_WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("Hệ thống chưa cấu hình biến môi trường ODO_SHEET_WEBHOOK_URL.")
            
        # Gửi toàn bộ ảnh và dữ liệu lên Apps Script Webhook
        sheet_resp = await upload_to_google_sheet(webhook_url, metadata, image_parts)
        
        if sheet_resp.get("status") == "success":
            file_url = sheet_resp.get("file_url", "")
            km_di_chuyen = metadata["odo_ve"] - metadata["odo_di"]
            
            await status_message.edit_text(
                f"✅ **ĐÃ GHI NHẬN DỮ LIỆU THÀNH CÔNG!**\n\n"
                f"📍 **Kho**: {metadata['ten_kho']} (ID: {metadata['id_kho']})\n"
                f"🚛 **Nhà xe (NCC)**: {metadata['ncc']}\n"
                f"🔢 **Biển Số**: {metadata['bien_so']}\n"
                f"📅 **Ngày**: {metadata['ngay']}\n"
                f"🚀 **Số KM đi (Sáng)**: {metadata['odo_di']:,} km\n"
                f"🏁 **Số KM về (Chiều)**: {metadata['odo_ve']:,} km\n"
                f"📈 **Tổng quãng đường di chuyển**: {km_di_chuyen:,} km\n\n"
                f"📁 [Xem hình ảnh lưu trữ trên Google Drive]({file_url})",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        else:
            raise RuntimeError(sheet_resp.get("message", "Lỗi không xác định khi lưu lên Google Sheets."))
            
    except Exception as e:
        print(f"[BOT ERROR] Xử lý thất bại: {e}")
        await status_message.edit_text(f"❌ **Xử lý thất bại!**\nChi tiết lỗi: `{str(e)}`", parse_mode="Markdown")

# Trì hoãn xử lý Album để đảm bảo nhận đủ tin nhắn
async def delayed_process_media_group(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(1.5)
    await process_media_group(media_group_id, context)

# Handler tiếp nhận và xử lý tin nhắn hình ảnh từ người dùng
async def handle_odo_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
        
    # Yêu cầu gửi ảnh kèm caption
    if not message.photo:
        await message.reply_text("❌ Vui lòng gửi ảnh chụp đồng hồ ODO của xe kèm theo nội dung mô tả chuyến đi.")
        return
        
    media_group_id = message.media_group_id
    if media_group_id:
        # Nếu là ảnh thuộc Album (Media Group)
        if media_group_id not in MEDIA_GROUPS:
            MEDIA_GROUPS[media_group_id] = {
                "messages": [message],
                "task": asyncio.create_task(delayed_process_media_group(media_group_id, context))
            }
        else:
            MEDIA_GROUPS[media_group_id]["messages"].append(message)
    else:
        # Nếu là 1 ảnh đơn lẻ
        group_id = f"single_{message.message_id}"
        MEDIA_GROUPS[group_id] = {
            "messages": [message],
            "task": None
        }
        await process_media_group(group_id, context)

# Trạng thái hoạt động của Bot để phục vụ API chẩn đoán
BOT_STATUS = {
    "initialized": False,
    "running": False,
    "last_error": None,
    "token_preview": None,
    "gemini_preview": None,
    "gemini_status": "Chưa kiểm tra",
    "webhook_preview": None,
    "logs": []
}

def log_status(message: str):
    print(f"[TELEGRAM BOT] {message}")
    BOT_STATUS["logs"].append(message)
    if len(BOT_STATUS["logs"]) > 50:
        BOT_STATUS["logs"].pop(0)

# Hàm chạy bot trong nền
async def run_bot():
    global BOT_STATUS
    import traceback
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    webhook_url = os.environ.get("ODO_SHEET_WEBHOOK_URL")
    
    BOT_STATUS["token_preview"] = f"{token[:6]}...{token[-4:]}" if token else "Không có"
    BOT_STATUS["gemini_preview"] = f"{gemini_key[:6]}...{gemini_key[-4:]}" if gemini_key else "Không có"
    BOT_STATUS["webhook_preview"] = f"{webhook_url[:15]}..." if webhook_url else "Không có"
    
    # Kiểm tra định dạng API Key Gemini của người dùng
    if gemini_key:
        if gemini_key.startswith("AIzaSy") or gemini_key.startswith("AQ."):
            BOT_STATUS["gemini_status"] = "Định dạng hợp lệ"
        elif gemini_key.startswith("AKfy"):
            BOT_STATUS["gemini_status"] = "Định dạng KHÔNG hợp lệ! (Có vẻ bạn đã copy nhầm ID Google Apps Script làm GEMINI_API_KEY)"
        else:
            BOT_STATUS["gemini_status"] = "Có vẻ hợp lệ (vui lòng đảm bảo đây là API Key lấy từ AI Studio)"
    else:
        BOT_STATUS["gemini_status"] = "Chưa cấu hình"

    if not token:
        log_status("WARNING: Biến TELEGRAM_BOT_TOKEN chưa được cấu hình. Bỏ qua khởi động bot.")
        return
        
    log_status("Đang khởi động Telegram Bot...")
    
    retry_delay = 10
    while True:
        try:
            # Khởi tạo application
            application = Application.builder().token(token).build()
            
            # Đăng ký handler lắng nghe tin nhắn có hình ảnh
            application.add_handler(MessageHandler(filters.PHOTO, handle_odo_submission))
            
            # Khởi chạy bot dạng polling
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            BOT_STATUS["initialized"] = True
            BOT_STATUS["running"] = True
            BOT_STATUS["last_error"] = None
            log_status("Bot đã khởi động thành công và đang lắng nghe tin nhắn.")
            
            # Giữ bot chạy vô hạn (nền)
            while True:
                await asyncio.sleep(3600)
                
        except Exception as e:
            err_msg = f"Lỗi chạy Bot: {str(e)}"
            log_status(err_msg)
            BOT_STATUS["last_error"] = f"{err_msg}\n{traceback.format_exc()}"
            BOT_STATUS["running"] = False
            
            # Đợi một chút rồi thử lại (tránh trường hợp xung đột cổng/instance tạm thời)
            log_status(f"Thử lại sau {retry_delay} giây...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay + 10, 60)
