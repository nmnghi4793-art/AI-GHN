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

# Sử dụng Google Gemini Vision để nhận diện 2 số ODO đi và về từ ảnh
async def read_odo_with_gemini(image_data: bytes) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình biến môi trường GEMINI_API_KEY trên hệ thống.")
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (
        "Hãy phân tích hình ảnh bảng đồng hồ công tơ mét này của xe ô tô và đọc số ODO đi (lúc sáng, giá trị nhỏ hơn) và số ODO về (lúc chiều, giá trị lớn hơn).\n"
        "Lưu ý: Bức ảnh có thể là ảnh ghép dọc chứa 2 đồng hồ ODO được chụp tại hai thời điểm khác nhau (ví dụ: sáng 08:28 ODO 441092 và chiều 14:59 ODO 441161).\n"
        "Đọc kỹ phần số ODO màu cam hiển thị trên màn hình LCD (chỉ lấy phần số nguyên, bỏ chữ km và các ký tự khác).\n"
        "Nếu ảnh chỉ có 1 đồng hồ ODO hiển thị duy nhất, hãy gán giá trị đó cho cả odo_di và odo_ve.\n\n"
        "Trả về kết quả dưới định dạng JSON duy nhất như sau (KHÔNG chứa khối mã markdown ```json):\n"
        "{\n"
        "  \"odo_di\": <số_km_đi>,\n"
        "  \"odo_ve\": <số_km_về>\n"
        "}"
    )
    
    image_part = {
        "mime_type": "image/jpeg",
        "data": image_data
    }
    
    # Thực hiện tác vụ gọi API đồng bộ trong ThreadPool để tránh block event loop của FastAPI
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        response = await loop.run_in_executor(
            pool, 
            lambda: model.generate_content([prompt, image_part])
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
        # Dùng Regex làm phương án dự phòng khẩn cấp
        odo_di_match = re.search(r'"odo_di"\s*:\s*(\d+)', text_response)
        odo_ve_match = re.search(r'"odo_ve"\s*:\s*(\d+)', text_response)
        return {
            "odo_di": int(odo_di_match.group(1)) if odo_di_match else 0,
            "odo_ve": int(odo_ve_match.group(1)) if odo_ve_match else 0
        }

# Gửi dữ liệu và file ảnh (dạng base64) lên Google Apps Script Webhook
async def upload_to_google_sheet(webhook_url: str, metadata: dict, image_data: bytes, filename: str) -> dict:
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    payload = {
        "id_kho": metadata.get("id_kho", ""),
        "ten_kho": metadata.get("ten_kho", ""),
        "ncc": metadata.get("ncc", ""),
        "odo_di": metadata.get("odo_di", 0),
        "odo_ve": metadata.get("odo_ve", 0),
        "ngay": metadata.get("ngay", ""),
        "bien_so": metadata.get("bien_so", ""),
        "image_base64": image_base64,
        "image_name": filename
    }
    
    async with httpx.AsyncClient() as client:
        # Google Apps Script có redirect (HTTP 302) nên bắt buộc phải có follow_redirects=True
        resp = await client.post(webhook_url, json=payload, follow_redirects=True, timeout=60.0)
        
    if resp.status_code == 200:
        return resp.json()
    else:
        raise RuntimeError(f"Google Webhook phản hồi lỗi {resp.status_code}: {resp.text}")

# Handler tiếp nhận và xử lý tin nhắn hình ảnh từ người dùng
async def handle_odo_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
        
    # Yêu cầu gửi ảnh kèm caption
    if not message.photo:
        await message.reply_text("❌ Vui lòng gửi ảnh chụp đồng hồ ODO của xe kèm theo nội dung mô tả chuyến đi.")
        return
        
    caption = message.caption
    if not caption:
        await message.reply_text(
            "❌ Vui lòng nhập nội dung mô tả kèm theo ảnh.\n\n"
            "Mẫu mô tả:\n"
            "1. 21089000 - Kho Giao Hàng Nặng Liên Chiểu - Đà Nẵng\n"
            "2. NCC Mạnh Cường Khánh Hoà\n"
            "3. Ngày 01/06/2026\n"
            "4. Biển Số Xe : 43H00912"
        )
        return
        
    status_message = await message.reply_text("⏳ Đang tải ảnh và phân tích dữ liệu ODO bằng AI, vui lòng đợi trong giây lát...")
    
    try:
        # 1. Tách thông tin mô tả văn bản
        metadata = parse_caption(caption)
        
        # 2. Tải ảnh chất lượng cao nhất về bộ nhớ
        photo = message.photo[-1]
        file = await photo.get_file()
        photo_bytes = await file.download_as_bytearray()
        photo_data = bytes(photo_bytes)
        
        # 3. Sử dụng Gemini đọc ODO
        await status_message.edit_text("⏳ AI đang nhận diện chỉ số ODO từ hình ảnh...")
        odo_results = await read_odo_with_gemini(photo_data)
        metadata["odo_di"] = odo_results.get("odo_di", 0)
        metadata["odo_ve"] = odo_results.get("odo_ve", 0)
        
        # Kiểm tra tính hợp lệ của ODO
        if metadata["odo_di"] == 0 and metadata["odo_ve"] == 0:
            raise ValueError("Không tìm thấy chỉ số ODO hợp lệ từ ảnh. Vui lòng chụp rõ màn hình ODO màu cam và gửi lại.")
            
        # 4. Gửi dữ liệu lên Google Sheets
        await status_message.edit_text("⏳ Đang lưu dữ liệu và lưu trữ ảnh lên Google Drive...")
        webhook_url = os.environ.get("ODO_SHEET_WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("Hệ thống chưa cấu hình biến môi trường ODO_SHEET_WEBHOOK_URL.")
            
        filename = f"odo_{metadata['bien_so']}_{metadata['ngay'].replace('/', '-')}.jpg"
        sheet_resp = await upload_to_google_sheet(webhook_url, metadata, photo_data, filename)
        
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
        if gemini_key.startswith("AIzaSy"):
            BOT_STATUS["gemini_status"] = "Định dạng hợp lệ (bắt đầu bằng AIzaSy)"
        else:
            BOT_STATUS["gemini_status"] = "Định dạng KHÔNG hợp lệ! (Khoá Gemini phải bắt đầu bằng AIzaSy. Có vẻ bạn đã copy nhầm ID Google Apps Script làm GEMINI_API_KEY)"
    else:
        BOT_STATUS["gemini_status"] = "Chưa cấu hình"

    if not token:
        log_status("WARNING: Biến TELEGRAM_BOT_TOKEN chưa được cấu hình. Bỏ qua khởi động bot.")
        return
        
    log_status("Đang khởi động Telegram Bot...")
    
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
        log_status("Bot đã khởi động thành công và đang lắng nghe tin nhắn.")
        
        # Giữ bot chạy vô hạn (nền)
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        err_msg = f"Lỗi khởi động Bot: {str(e)}\n{traceback.format_exc()}"
        log_status(err_msg)
        BOT_STATUS["last_error"] = err_msg
        BOT_STATUS["running"] = False

