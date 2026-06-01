import os
import re
import json
import base64
import asyncio
import httpx
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import html


# Bộ nhớ đệm lưu trữ các tin nhắn thuộc cùng một Album (Media Group)
MEDIA_GROUPS = {}

def compress_image(image_bytes: bytes, max_size=(1024, 1024), quality=80) -> bytes:
    from PIL import Image
    import io
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        out_io = io.BytesIO()
        img.save(out_io, format='JPEG', quality=quality)
        compressed = out_io.getvalue()
        print(f"[BOT] Compressed image: {len(image_bytes)} bytes -> {len(compressed)} bytes")
        return compressed
    except Exception as e:
        print(f"[BOT] Error compressing image: {e}")
        return image_bytes


# --- STATE AND HELPER FUNCTIONS FOR ODO TRACKING ---
def save_local_state(date_str: str, submission: dict = None, off_report: dict = None):
    state_file = "odo_state.json"
    state_data = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
        except Exception as e:
            print(f"[BOT] Error reading state file before save: {e}")
            
    if date_str not in state_data:
        state_data[date_str] = {
            "submissions": [],
            "off_reports": {}
        }
        
    if submission:
        # Check if already exists to avoid duplicates
        exists = False
        for s in state_data[date_str]["submissions"]:
            if s.get("bien_so") == submission.get("bien_so") and s.get("id_kho") == submission.get("id_kho"):
                exists = True
                break
        if not exists:
            state_data[date_str]["submissions"].append(submission)
            
    if off_report:
        id_kho = off_report.get("id_kho")
        ten_kho = off_report.get("ten_kho")
        off_count = off_report.get("off_count", 0)
        key = id_kho if id_kho else ten_kho
        
        current_off = state_data[date_str]["off_reports"].get(key, 0)
        state_data[date_str]["off_reports"][key] = current_off + off_count
        
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[BOT] Error writing state file: {e}")

def get_today_submissions(target_date_str: str):
    # target_date_str format: "01/06/2026"
    submissions = {}
    
    # 1. Read from local state file
    state_file = "odo_state.json"
    local_subs = []
    local_offs = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            day_data = state_data.get(target_date_str, {})
            local_subs = day_data.get("submissions", [])
            local_offs = day_data.get("off_reports", {})
        except Exception as e:
            print(f"[BOT] Error reading local state file: {e}")
            
    # 2. Read from Google Sheet if GID is provided
    odo_gid = os.environ.get("ODO_SHEET_GID")
    sheet_subs = []
    if odo_gid:
        try:
            from main import read_csv, GIDS
            if "odo_sheet" not in GIDS:
                GIDS["odo_sheet"] = odo_gid
            # force read_csv to fetch latest
            data, _ = read_csv("odo_sheet", force=True)
            for r in data:
                r_date = r.get("Ngày") or r.get("ngay") or ""
                if r_date.strip() == target_date_str:
                    id_kho = r.get("ID Kho") or r.get("id_kho") or ""
                    ten_kho = r.get("Tên kho") or r.get("ten_kho") or ""
                    bien_so = r.get("Biển Số Xe") or r.get("Biển số xe") or r.get("bien_so") or ""
                    sheet_subs.append({
                        "id_kho": id_kho.strip(),
                        "ten_kho": ten_kho.strip(),
                        "bien_so": bien_so.strip().upper()
                    })
        except Exception as e:
            print(f"[BOT] Error fetching ODO submissions from Google Sheet: {e}")
            
    merged_subs = {}
    for sub in local_subs + sheet_subs:
        id_kho = sub.get("id_kho")
        ten_kho = sub.get("ten_kho")
        bien_so = sub.get("bien_so")
        key = id_kho if id_kho else ten_kho
        if not key:
            continue
        if key not in merged_subs:
            merged_subs[key] = []
        if bien_so not in merged_subs[key]:
            merged_subs[key].append(bien_so)
            
    return merged_subs, local_offs

def get_gxt_vehicles_count():
    try:
        from main import read_csv
        data, _ = read_csv("xe_gxt")
        vehicles_count = {}
        for r in data:
            kho = r.get("Kho") or r.get("Tên Kho GXT") or r.get("Kho giao") or ""
            if not kho:
                continue
            
            count_str = r.get("Tổng xe đang chạy") or r.get("Tổng xe") or "0"
            try:
                count_str = str(count_str).replace(".", "").replace(",", "").strip()
                count = int(count_str) if count_str else 0
            except:
                count = 0
                
            if count <= 0:
                continue
                
            m = re.search(r'(\d{5,12})', kho)
            id_kho = m.group(1) if m else ""
            
            ten_kho = kho
            if id_kho and id_kho in kho:
                parts = kho.split('-', 1)
                if len(parts) == 2:
                    ten_kho = parts[1].strip()
                else:
                    ten_kho = kho.replace(id_kho, "").replace("-", "").strip()
                    
            key = id_kho if id_kho else ten_kho
            if not key:
                continue
                
            if key not in vehicles_count:
                vehicles_count[key] = {
                    "id_kho": id_kho,
                    "ten_kho": ten_kho,
                    "full_name": kho,
                    "total_vehicles": 0
                }
            vehicles_count[key]["total_vehicles"] += count
            
        return vehicles_count
    except Exception as e:
        print(f"[BOT ERROR] Error fetching registered vehicles: {e}")
        return {}

def generate_odo_warning_report(date_str: str) -> str:
    registered = get_gxt_vehicles_count()
    if not registered:
        return "⚠️ Không thể tải dữ liệu xe GXT từ Google Sheet để so sánh."
        
    submissions, off_reports = get_today_submissions(date_str)
    
    warning_lines = []
    total_missing_all = 0
    total_expected_all = 0
    total_submitted_all = 0
    
    for key, info in registered.items():
        id_kho = info["id_kho"]
        ten_kho = info["ten_kho"]
        total_vehicles = info["total_vehicles"]
        
        off_count = off_reports.get(id_kho, 0)
        if not off_count and not id_kho:
            off_count = off_reports.get(ten_kho, 0)
            
        target_vehicles = max(0, total_vehicles - off_count)
        
        subs_list = submissions.get(id_kho, [])
        if not subs_list and not id_kho:
            subs_list = submissions.get(ten_kho, [])
            
        submitted_count = len(subs_list)
        missing_count = max(0, target_vehicles - submitted_count)
        
        total_expected_all += target_vehicles
        total_submitted_all += submitted_count
        total_missing_all += missing_count
        
        if missing_count > 0:
            off_str = f" (Off {off_count} xe)" if off_count > 0 else ""
            warning_lines.append(
                f"• <b>{html.escape(ten_kho)}</b>{f' ({html.escape(id_kho)})' if id_kho else ''}:\n"
                f"  - Yêu cầu: {target_vehicles} xe{off_str}\n"
                f"  - Đã nhập: {submitted_count} xe\n"
                f"  - 🔴 <b>Thiếu: {missing_count} xe</b>"
            )
            
    msg = f"📊 <b>BÁO CÁO CẢNH BÁO CHƯA NHẬP ODO - NGÀY {date_str}</b>\n\n"
    if warning_lines:
        msg += f"🚨 <b>Danh sách các kho chưa nhập đủ ODO:</b>\n"
        msg += "\n".join(warning_lines)
        msg += "\n\n"
        msg += f"📈 <b>Tổng quan toàn mạng lưới:</b>\n"
        msg += f"  - Tổng xe yêu cầu: {total_expected_all} xe\n"
        msg += f"  - Tổng xe đã nhập: {total_submitted_all} xe\n"
        msg += f"  - Tổng xe chưa nhập: {total_missing_all} xe\n"
    else:
        msg += f"🎉 <b>Tất cả các kho đã nhập đủ chỉ số ODO cho ngày hôm nay!</b>\n"
        msg += f"  - Tổng số xe hoạt động: {total_expected_all} xe\n"
        
    return msg

async def scheduled_warning_loop(application):
    print("[BOT] Scheduled warning loop started.")
    tz_utc_7 = dt.timezone(dt.timedelta(hours=7))
    last_sent_date = ""
    
    while True:
        try:
            await asyncio.sleep(30)
            now_local = dt.datetime.now(tz_utc_7)
            current_date = now_local.strftime("%d/%m/%Y")
            current_time = now_local.strftime("%H:%M")
            
            warn_time = os.environ.get("WARN_TIME", "22:00")
            warn_chat_id = os.environ.get("WARN_CHAT_ID", "-1002712779761")
            
            if current_time == warn_time and last_sent_date != current_date:
                report_msg = generate_odo_warning_report(current_date)
                await application.bot.send_message(
                    chat_id=warn_chat_id,
                    text=report_msg,
                    parse_mode="HTML"
                )
                print(f"[BOT] Daily warning report sent for {current_date}")
                last_sent_date = current_date
        except Exception as e:
            print(f"[BOT ERROR] Error in scheduled warning loop: {e}")

def parse_off_report(text: str) -> dict:
    if not text:
        return None
        
    match_off = re.search(r'(?i)\boff\s*(\d+)\s*xe', text)
    if not match_off:
        match_off = re.search(r'(?i)\boff\s*(\d+)', text)
        
    if not match_off:
        return None
        
    off_count = int(match_off.group(1))
    
    id_kho = ""
    match_id = re.search(r'\b(\d{5,12})\b', text)
    if match_id:
        id_kho = match_id.group(1)
        
    ten_kho = ""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines:
        if id_kho and id_kho in line:
            parts = line.split('-', 1)
            if len(parts) == 2:
                ten_kho = parts[1].strip()
            else:
                ten_kho = line.replace(id_kho, "").replace("-", "").strip()
            break
        elif "kho" in line.lower() and not "off" in line.lower():
            ten_kho = line
            break
            
    ngay = ""
    match_date = re.search(r'(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})', text)
    if match_date:
        ngay = match_date.group(1)
    else:
        tz_utc_7 = dt.timezone(dt.timedelta(hours=7))
        now_local = dt.datetime.now(tz_utc_7)
        ngay = now_local.strftime("%d/%m/%Y")
        
    return {
        "id_kho": id_kho,
        "ten_kho": ten_kho,
        "ngay": ngay,
        "off_count": off_count
    }

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
        
    off_report = parse_off_report(message.text)
    if off_report:
        registered_khos = get_gxt_vehicles_count()
        id_kho = off_report["id_kho"]
        ten_kho = off_report["ten_kho"]
        
        matched_kho = None
        if id_kho:
            matched_kho = registered_khos.get(id_kho)
            
        if not matched_kho and ten_kho:
            for k_key, k_val in registered_khos.items():
                if ten_kho.lower() in k_val["ten_kho"].lower() or k_val["ten_kho"].lower() in ten_kho.lower():
                    matched_kho = k_val
                    break
                    
        if matched_kho:
            off_report["id_kho"] = matched_kho["id_kho"]
            off_report["ten_kho"] = matched_kho["ten_kho"]
            
        save_local_state(off_report["ngay"], off_report=off_report)
        
        ten_display = off_report["ten_kho"] if off_report["ten_kho"] else "Chưa rõ tên"
        id_display = f" (ID: {off_report['id_kho']})" if off_report["id_kho"] else ""
        
        await message.reply_text(
            f"✅ <b>ĐÃ GHI NHẬN THÔNG TIN XE OFF!</b>\n\n"
            f"📍 <b>Kho</b>: {html.escape(ten_display)}{html.escape(id_display)}\n"
            f"📅 <b>Ngày</b>: {html.escape(off_report['ngay'])}\n"
            f"🚫 <b>Số xe off</b>: {off_report['off_count']} xe\n\n"
            f"Cuối ngày BOT sẽ tự động trừ xe off khi tổng hợp báo cáo ODO.",
            parse_mode="HTML"
        )

def clean_line_prefix(line: str) -> str:
    line = line.strip()
    m = re.match(r'^([1-9])\s*[\.\:\-]\s*(.*)$', line)
    if m:
        return m.group(2).strip()
    m = re.match(r'^([1-9])\s+(.*)$', line)
    if m:
        if not re.match(r'^[0-9]{1,2}[-\/][0-9]{2,4}', line):
            return m.group(2).strip()
    return line

# Cắt chuỗi và trích xuất dữ liệu từ caption của người dùng
def parse_caption(text: str) -> dict:
    if not text:
        return {}
    
    raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
    lines = [clean_line_prefix(line) for line in raw_lines]
    
    result = {
        "id_kho": "",
        "ten_kho": "",
        "ncc": "",
        "ngay": "",
        "bien_so": "",
        "loai_xe": ""
    }
    
    # 1. Nhận diện các dòng dựa trên từ khóa hoặc định dạng rõ ràng
    warehouse_line = None
    ncc_line = None
    date_line = None
    plate_line = None
    loai_xe_line = None
    
    for line in lines:
        line_lower = line.lower()
        
        # Nhận diện dòng Kho (có chứa mã kho 5-12 số và dấu gạch ngang, hoặc chứa từ "kho")
        if re.search(r'\d{5,12}\s*-\s*', line) or "kho" in line_lower:
            warehouse_line = line
        # Nhận diện dòng Ngày (có định dạng ngày xx/xx/xxxx hoặc xx-xx-xxxx, hoặc chứa từ "ngày"/"ngay")
        elif re.search(r'\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}', line) or "ngày" in line_lower or "ngay" in line_lower:
            date_line = line
        # Nhận diện dòng Biển Số (có chứa các từ khóa liên quan đến biển số)
        elif any(k in line_lower for k in ["biển", "bien", "số xe", "so xe"]):
            plate_line = line
        # Nhận diện dòng Loại Xe
        elif "loại xe" in line_lower or "loai xe" in line_lower:
            loai_xe_line = line
        # Nhận diện dòng NCC (có chứa từ "ncc")
        elif "ncc" in line_lower:
            ncc_line = line
        # Nhận diện trực tiếp Loại Xe qua từ khóa trong dòng
        elif "cố định" in line_lower or "co dinh" in line_lower:
            result["loai_xe"] = "Xe Cố Định"
        elif "tăng cường" in line_lower or "tang cuong" in line_lower:
            result["loai_xe"] = "Xe Tăng Cường"

    # 2. Trích xuất thông tin từ các dòng đã nhận diện
    if warehouse_line:
        m = re.search(r'(\d{5,12})\s*-\s*(.*)', warehouse_line)
        if m:
            result["id_kho"] = m.group(1).strip()
            result["ten_kho"] = m.group(2).strip()
        else:
            parts = warehouse_line.split('-', 1)
            if len(parts) == 2:
                result["id_kho"] = "".join(c for c in parts[0] if c.isdigit())
                result["ten_kho"] = parts[1].strip()
            else:
                result["ten_kho"] = warehouse_line
                
    if ncc_line:
        clean = re.sub(r'^ncc\s*', '', ncc_line, flags=re.IGNORECASE).strip()
        clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
        result["ncc"] = clean
        
    if date_line:
        m = re.search(r'(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})', date_line)
        if m:
            result["ngay"] = m.group(1).strip()
        else:
            clean = re.sub(r'^ng[àa]y\s*', '', date_line, flags=re.IGNORECASE).strip()
            clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
            result["ngay"] = clean
            
    if plate_line:
        clean = re.sub(r'^(biển số xe|bien so xe|biển số|bien so|biển|bien|số xe|so xe)\s*', '', plate_line, flags=re.IGNORECASE).strip()
        clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
        result["bien_so"] = clean.upper()

    if loai_xe_line and not result["loai_xe"]:
        clean = re.sub(r'^(loại xe|loai xe)\s*', '', loai_xe_line, flags=re.IGNORECASE).strip()
        clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
        if "tăng cường" in clean.lower() or "tang cuong" in clean.lower():
            result["loai_xe"] = "Xe Tăng Cường"
        else:
            result["loai_xe"] = "Xe Cố Định"

    # 3. Fallback: Nếu có ít nhất 4 dòng và một số trường thông tin vẫn bị thiếu
    if len(lines) >= 4:
        # Dòng 0: Kho
        if not result["id_kho"] or not result["ten_kho"]:
            m = re.search(r'(\d{5,12})\s*-\s*(.*)', lines[0])
            if m:
                result["id_kho"] = m.group(1).strip()
                result["ten_kho"] = m.group(2).strip()
            else:
                parts = lines[0].split('-', 1)
                if len(parts) == 2:
                    result["id_kho"] = "".join(c for c in parts[0] if c.isdigit())
                    result["ten_kho"] = parts[1].strip()
                else:
                    result["ten_kho"] = lines[0]
                    
        # Dòng 1: NCC
        if not result["ncc"]:
            clean = re.sub(r'^ncc\s*', '', lines[1], flags=re.IGNORECASE).strip()
            clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
            result["ncc"] = clean
            
        # Dòng 2: Ngày
        if not result["ngay"]:
            m = re.search(r'(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4})', lines[2])
            if m:
                result["ngay"] = m.group(1).strip()
            else:
                clean = re.sub(r'^ng[àa]y\s*', '', lines[2], flags=re.IGNORECASE).strip()
                clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
                result["ngay"] = clean
                
        # Dòng 3: Biển Số
        if not result["bien_so"]:
            clean = re.sub(r'^(biển số xe|bien so xe|biển số|bien so|biển|bien|số xe|so xe)\s*', '', lines[3], flags=re.IGNORECASE).strip()
            clean = re.sub(r'^[\:\-]\s*', '', clean).strip()
            result["bien_so"] = clean.upper()

        # Dòng 4: Loại xe
        if len(lines) >= 5 and not result["loai_xe"]:
            clean = lines[4].strip()
            if "tăng cường" in clean.lower() or "tang cuong" in clean.lower():
                result["loai_xe"] = "Xe Tăng Cường"
            else:
                result["loai_xe"] = "Xe Cố Định"

    # Mặc định Loại Xe nếu không tìm thấy
    if not result["loai_xe"]:
        result["loai_xe"] = "Xe Cố Định"

    # 4. Làm sạch triệt để các khoảng trắng thừa
    for k in result:
        result[k] = result[k].strip()
    if result["bien_so"]:
        result["bien_so"] = result["bien_so"].upper()
        
    return result

# Bộ nhớ đệm lưu model Gemini đã dò tìm để tăng tốc xử lý
CACHED_GEMINI_MODEL = None

# Sử dụng Google Gemini Vision để nhận diện chỉ số ODO từ các hình ảnh
async def read_odo_with_gemini(image_parts: list) -> dict:
    global CACHED_GEMINI_MODEL
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình biến môi trường GEMINI_API_KEY trên hệ thống.")
        
    genai.configure(api_key=api_key)
    
    if not CACHED_GEMINI_MODEL:
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
            CACHED_GEMINI_MODEL = model_name
        except Exception as e:
            print(f"[GEMINI WARNING] Không thể lấy danh sách model, sử dụng mặc định {model_name}. Lỗi: {e}")
            CACHED_GEMINI_MODEL = model_name
            
    model = genai.GenerativeModel(CACHED_GEMINI_MODEL)
    
    prompt = (
        "Hãy phân tích các hình ảnh bảng đồng hồ công tơ mét này của xe ô tô và đọc số ODO đi (lúc sáng, giá trị nhỏ hơn) và số ODO về (lúc chiều, giá trị lớn hơn).\n"
        "Nếu người dùng gửi 2 ảnh khác nhau (trong album):\n"
        "  - 1 ảnh là lúc đi (giá trị ODO nhỏ hơn, thường chụp buổi sáng).\n"
        "  - 1 ảnh là lúc về (giá trị ODO lớn hơn, thường chụp buổi chiều).\n"
        "Hãy so sánh và xác định chính xác số ODO đi (odo_di) và số ODO về (odo_ve).\n"
        "Nếu chỉ có 1 ảnh duy nhất (hoặc các ảnh có cùng chỉ số ODO), hãy gán giá trị đó cho cả odo_di và odo_ve.\n\n"
        "HƯỚNG DẪN ĐỌC SỐ ODO:\n"
        "  - CHỈ đọc số ODO chính (dãy số ODO tổng hành trình thường có 6 chữ số, ví dụ như 209806).\n"
        "  - BỎ QUA chỉ số TRIP/hành trình ngắn (thường có 3-4 chữ số kèm 1 chữ số thập phân ở cuối, thường nằm dưới kim chỉ tốc độ hoặc có nền màu trắng khác biệt ở ô số cuối).\n"
        "  - Chỉ lấy phần số nguyên, bỏ chữ km và các ký tự khác.\n\n"
        "QUAN TRỌNG: Nếu hình ảnh quá mờ, loá sáng, không rõ nét, hoặc bị che khuất khiến bạn KHÔNG THỂ đọc được số ODO một cách chính xác, "
        "hãy trả về JSON có thuộc tính \"blurry\": true. Đừng cố đoán mò nếu số bị loè hoặc quá mờ.\n\n"
        "Trả về kết quả dưới định dạng JSON duy nhất như sau (KHÔNG chứa khối mã markdown ```json):\n"
        "{\n"
        "  \"blurry\": <true_hoặc_false>,\n"
        "  \"odo_di\": <số_km_đi_hoặc_0>,\n"
        "  \"odo_ve\": <số_km_về_hoặc_0>\n"
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
        data = json.loads(text_response)
        return {
            "blurry": data.get("blurry", False),
            "odo_di": data.get("odo_di", 0),
            "odo_ve": data.get("odo_ve", 0)
        }
    except Exception as e:
        print(f"[GEMINI ERROR] Lỗi phân tích cú pháp JSON: {text_response}. Chi tiết: {e}")
        odo_di_match = re.search(r'"odo_di"\s*:\s*(\d+)', text_response)
        odo_ve_match = re.search(r'"odo_ve"\s*:\s*(\d+)', text_response)
        blurry_match = re.search(r'"blurry"\s*:\s*(true|false)', text_response, re.IGNORECASE)
        return {
            "blurry": (blurry_match.group(1).lower() == "true") if blurry_match else False,
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
        "loai_xe": metadata.get("loai_xe", ""),
        "image_base64": images_payload[0]["base64"] if images_payload else "",
        "image_name": images_payload[0]["name"] if images_payload else "",
        "images": images_payload
    }
    
    async with httpx.AsyncClient() as client:
        # Google Apps Script có redirect (HTTP 302) nên bắt buộc phải có follow_redirects=True
        resp = await client.post(webhook_url, json=payload, follow_redirects=True, timeout=60.0)
        
    if resp.status_code == 200:
        return resp.json()
    else:
        raise RuntimeError(f"Google Webhook phản hồi lỗi {resp.status_code}: {resp.text}")

def normalize_plate(plate: str) -> str:
    if not plate:
        return ""
    return re.sub(r'[^A-Z0-9]', '', plate.upper())

ALLOWED_WAREHOUSES = {
    "21086000": "Kho Giao Hàng Nặng - Đông Thọ - Thanh Hóa",
    "21095000": "Kho Giao Hàng Nặng - Vinh - Nghệ An",
    "21682000": "Kho Giao Hàng Nặng - Thạch Linh - Hà Tĩnh",
    "21283000": "Kho Giao Hàng Nặng - Đồng Hới - Quảng Bình",
    "21521000": "Kho Giao Hàng Nặng - Đông Hà - Quảng Trị",
    "21096000": "Kho Giao Hàng Nặng - Hương Thủy - Huế",
    "21089000": "Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng",
    "22059000": "Kho Giao Hàng Nặng - Hòa Xuân - Đà Nẵng",
    "21386000": "Kho Giao Hàng Nặng - Hội An - Quảng Nam",
    "21483000": "Kho Giao Hàng Nặng - Tam Kỳ - Quảng Nam",
    "21284000": "Kho Giao Hàng Nặng - Quảng Ngãi - Quảng Ngãi",
    "21162000": "Kho Giao Hàng Nặng - Thắng Lợi - Kon Tum",
    "21091000": "Kho Giao Hàng Nặng - Pleiku - Gia Lai",
    "21090000": "Kho Giao Hàng Nặng - Buôn Ma Thuột - Đắk Lắk",
    "22782000": "Kho Giao Hàng Nặng - Buôn Hồ - Đắk Lắk",
    "21525000": "Kho Giao Hàng Nặng - Gia Nghĩa - Đắk Nông",
    "22168000": "Kho Giao Hàng Nặng - Hoài Nhơn - Bình Định",
    "21087000": "Kho Giao Hàng Nặng - Quy Nhơn - Bình Định",
    "21347000": "Kho Giao Hàng Nặng - Tuy Hòa - Phú Yên",
    "21094000": "Kho Giao Hàng Nặng - Nha Trang - Khánh Hòa",
    "21498000": "Kho Giao Hàng Nặng - Cam Ranh - Khánh Hòa",
    "21163000": "Kho Giao Hàng Nặng - Phan Rang - Ninh Thuận",
    "22057000": "Kho Giao Hàng Nặng - Tuy Phong - Bình Thuận",
    "21285000": "Kho Giao Hàng Nặng - Phan Thiết - Bình Thuận",
    "22028000": "Kho Giao Hàng Nặng - La Gi - Bình Thuận"
}

ALLOWED_NCC = [
    "Ngọc Định", "Tín Thành", "An Logistics", "Minh Đăng", "Lã Mạnh Hùng", 
    "Hải Đăng", "Nguyễn Mạnh Đà Nẵng", "Trần Xuân Phúc", "Thần Đèn", "HTL", 
    "Bảo Châu Phát", "Gia Hân", "Nguyễn Huy Logistics", "Đặng Ngọc Phúc", 
    "Tốt và Rẻ ĐN", "Gia Nghĩa", "Phú Hảo", "Quân Khang Phát", "Việt Bắc", 
    "Mạnh Cường Khánh Hòa", "Mạnh Cường Khánh Hoà", "NAK"
]

def clean_str(s: str) -> str:
    s = s.lower().strip()
    replacements = {
        'a': 'áàảãạăắằẳẵặâấầẩẫậa',
        'e': 'éèẻẽẹêếềểễệe',
        'i': 'íìỉĩịi',
        'o': 'óòỏõọôốồổỗộơớờởỡợo',
        'u': 'úùủũụưứừửữựu',
        'y': 'ýỳỷỹỵy',
        'd': 'đd'
    }
    for base, accents in replacements.items():
        for accent in accents:
            s = s.replace(accent, base)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def validate_caption_strict(text: str) -> tuple[bool, str, dict]:
    if not text:
        return False, "Nội dung mô tả trống.", {}
        
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) != 5:
        return False, (
            "Sai cấu trúc tin nhắn báo cáo! Cú pháp bắt buộc phải có đúng 5 dòng như sau:\n\n"
            "<code>[Mã Kho] - [Tên Kho]\n"
            "[Tên NCC]\n"
            "[Ngày dd/mm/yyyy]\n"
            "[Biển Số Xe]\n"
            "[Loại Xe]</code>\n\n"
            "Ví dụ mẫu chuẩn:\n"
            "<code>21089000 - Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng\n"
            "Mạnh Cường Khánh Hoà\n"
            "01/06/2026\n"
            "43H00912\n"
            "Xe Cố Định</code>"
        ), {}

    # Dòng 1: [Mã Kho] - [Tên Kho]
    warehouse_line = lines[0]
    match_wh = re.match(r'^(\d{5,12})\s*-\s*(.*)$', warehouse_line)
    if not match_wh:
        return False, "Dòng 1 sai cú pháp! Định dạng đúng phải là: <code>[Mã Kho] - [Tên Kho]</code> (Ví dụ: <code>21089000 - Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng</code>).", {}
        
    id_kho = match_wh.group(1).strip()
    ten_kho_input = match_wh.group(2).strip()
    
    if id_kho not in ALLOWED_WAREHOUSES:
        return False, f"Mã kho <code>{html.escape(id_kho)}</code> không tồn tại trong hệ thống hoặc không hợp lệ!", {}
        
    wh_expected = ALLOWED_WAREHOUSES[id_kho]
    if clean_str(ten_kho_input) != clean_str(wh_expected):
        return False, f"Tên kho không khớp với mã kho! Tên đúng của mã kho {id_kho} là: <code>{html.escape(wh_expected)}</code>.", {}
        
    # Dòng 2: Tên NCC
    ncc_input = lines[1]
    ncc_matched = None
    for ncc in ALLOWED_NCC:
        if clean_str(ncc_input) == clean_str(ncc):
            ncc_matched = ncc
            break
            
    if not ncc_matched:
        return False, f"Tên nhà cung cấp (NCC) <code>{html.escape(ncc_input)}</code> không hợp lệ hoặc không có trong danh sách được phép!", {}
        
    # Dòng 3: Ngày dd/mm/yyyy
    date_input = lines[2]
    if not re.match(r'^\d{2}/\d{2}/\d{4}$', date_input):
        return False, f"Định dạng ngày <code>{html.escape(date_input)}</code> không đúng! Vui lòng nhập đúng định dạng <code>dd/mm/yyyy</code> (Ví dụ: <code>01/06/2026</code>).", {}
        
    # Dòng 4: Biển số xe
    plate_input = lines[3]
    if not re.match(r'^[A-Z0-9]+$', plate_input.upper()):
        return False, f"Biển số xe <code>{html.escape(plate_input)}</code> không hợp lệ! Biển số xe bắt buộc phải viết liền không dấu gạch ngang (-), không có dấu chấm (.) hay khoảng trắng.", {}
        
    # Dòng 5: Loại Xe
    type_input = lines[4].strip()
    type_clean = clean_str(type_input)
    matched_type = None
    if type_clean == clean_str("Xe Cố Định"):
        matched_type = "Xe Cố Định"
    elif type_clean == clean_str("Xe Tăng Cường"):
        matched_type = "Xe Tăng Cường"
        
    if not matched_type:
        return False, f"Loại xe <code>{html.escape(type_input)}</code> không hợp lệ! Chỉ chấp nhận <code>Xe Cố Định</code> hoặc <code>Xe Tăng Cường</code>.", {}
        
    return True, "", {
        "id_kho": id_kho,
        "ten_kho": wh_expected,
        "ncc": ncc_matched,
        "ngay": date_input,
        "bien_so": plate_input.upper(),
        "loai_xe": matched_type
    }

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
        # Bỏ qua âm thầm nếu người dùng gửi hình ảnh không kèm mô tả (tránh làm phiền trong group chat)
        return
        
    # Kiểm tra xem có phải là nỗ lực gửi báo cáo ODO hay không (dòng đầu bắt đầu bằng mã kho 5-12 chữ số)
    lines_check = [line.strip() for line in caption.split('\n') if line.strip()]
    if not lines_check or not re.match(r'^\d{5,12}', lines_check[0]):
        # Không phải tin nhắn báo cáo ODO, bỏ qua âm thầm
        return
        
    # 1. Tách thông tin mô tả văn bản và kiểm tra tính hợp lệ nghiêm ngặt
    is_valid, error_msg, metadata = validate_caption_strict(caption)
    if not is_valid:
        alert_msg = (
            f"❌ <b>SAI CÚ PHÁP</b>\n\n"
            f"{error_msg}\n\n"
            f"Yêu cầu bạn chỉnh sửa lại nội dung tin nhắn cho đúng cú pháp theo mẫu:\n"
            f"<code>21089000 - Kho Giao Hàng Nặng - Liên Chiểu - Đà Nẵng\n"
            f"Mạnh Cường Khánh Hoà\n"
            f"01/06/2026\n"
            f"43H00912\n"
            f"Xe Cố Định</code>\n\n"
            f"cc: @Thu_Dieu_Admin_GXT"
        )
        await primary_message.reply_text(
            alert_msg,
            parse_mode="HTML"
        )
        return
        
    # Kiểm tra trùng lặp biển số xe trong ngày
    incoming_plate_norm = normalize_plate(metadata.get("bien_so"))
    if incoming_plate_norm:
        today_subs, _ = get_today_submissions(metadata["ngay"])
        all_plates_today = []
        for plates in today_subs.values():
            all_plates_today.extend(plates)
            
        if incoming_plate_norm in [normalize_plate(p) for p in all_plates_today]:
            alert_msg = (
                f"⚠️ <b>CẢNH BÁO: BIỂN SỐ XE {html.escape(metadata['bien_so'])} ĐÃ BÁO ODO TRONG NGÀY HÔM NAY {html.escape(metadata['ngay'])}</b>\n\n"
                f"Yêu cầu bạn kiểm tra lại thông tin. Báo cáo trùng lặp này không được ghi nhận.\n\n"
                f"cc: @Thu_Dieu_Admin_GXT"
            )
            await primary_message.reply_text(
                alert_msg,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            return
        
    status_message = await primary_message.reply_text("⏳ Đang tải ảnh và phân tích dữ liệu ODO bằng AI, vui lòng đợi trong giây lát...")
    
    try:
        # Đảm bảo có ngày tháng
        if not metadata.get("ngay"):
            tz_utc_7 = dt.timezone(dt.timedelta(hours=7))
            metadata["ngay"] = dt.datetime.now(tz_utc_7).strftime("%d/%m/%Y")
            
        # 2. Tải tất cả ảnh trong Album về bộ nhớ
        await status_message.edit_text(f"⏳ Đang tải {len(photos)} hình ảnh...")
        image_parts = []
        for i, photo in enumerate(photos):
            file = await photo.get_file()
            photo_bytes = await file.download_as_bytearray()
            compressed_bytes = compress_image(bytes(photo_bytes))
            image_parts.append({
                "mime_type": "image/jpeg",
                "data": compressed_bytes
            })
            
        # 3. Sử dụng Gemini đọc ODO từ các ảnh
        await status_message.edit_text("⏳ AI đang nhận diện chỉ số ODO từ các hình ảnh...")
        odo_results = await read_odo_with_gemini(image_parts)
        metadata["odo_di"] = odo_results.get("odo_di", 0)
        metadata["odo_ve"] = odo_results.get("odo_ve", 0)
        is_blurry = odo_results.get("blurry", False)
        
        # Kiểm tra hình ảnh quá mờ hoặc ODO bằng 0
        if is_blurry or (metadata["odo_di"] == 0 and metadata["odo_ve"] == 0):
            sheet_url = "https://docs.google.com/spreadsheets/d/1frGuwcXD3oTcvY8wt62CqA3j0i6Ub2YrksF_tUIFrcY/edit?gid=0#gid=0"
            alert_msg = (
                f"⚠️ <b>CẢNH BÁO: KHÔNG ĐỌC ĐƯỢC SỐ KM VÌ HÌNH ẢNH QUÁ MỜ</b>\n\n"
                f"Yêu cầu bạn gửi lại hình ảnh khác rõ nét hơn hoặc nhập số KM trực tiếp vào <a href=\"{sheet_url}\">link Google Sheet</a>.\n\n"
                f"cc: @Thu_Dieu_Admin_GXT"
            )
            await primary_message.reply_text(
                alert_msg,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await status_message.delete()
            return
            
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
            
            # Lưu lại trạng thái đã nộp ODO thành công
            save_local_state(
                metadata["ngay"],
                submission={
                    "id_kho": metadata.get("id_kho", ""),
                    "ten_kho": metadata.get("ten_kho", ""),
                    "bien_so": metadata.get("bien_so", "")
                }
            )
            
            success_msg = (
                f"✅ <b>ĐÃ GHI NHẬN DỮ LIỆU THÀNH CÔNG!</b>\n\n"
                f"📍 <b>Kho</b>: {html.escape(metadata['ten_kho'])} (ID: {html.escape(metadata['id_kho'])})\n"
                f"🚛 <b>Nhà xe (NCC)</b>: {html.escape(metadata['ncc'])}\n"
                f"🔢 <b>Biển Số</b>: {html.escape(metadata['bien_so'])}\n"
                f"🏷️ <b>Loại Xe</b>: {html.escape(metadata['loai_xe'])}\n"
                f"📅 <b>Ngày</b>: {html.escape(metadata['ngay'])}\n"
                f"🚀 <b>Số KM đi (Sáng)</b>: {metadata['odo_di']:,} km\n"
                f"🏁 <b>Số KM về (Chiều)</b>: {metadata['odo_ve']:,} km\n"
                f"📈 <b>Tổng quãng đường di chuyển</b>: {km_di_chuyen:,} km\n\n"
                f"📁 <a href=\"{html.escape(file_url)}\">Xem hình ảnh lưu trữ trên Google Drive</a>"
            )
            await status_message.edit_text(
                success_msg,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            raise RuntimeError(sheet_resp.get("message", "Lỗi không xác định khi lưu lên Google Sheets."))
            
    except Exception as e:
        print(f"[BOT ERROR] Xử lý thất bại: {e}")
        await status_message.edit_text(f"❌ <b>Xử lý thất bại!</b>\nChi tiết lỗi: <code>{html.escape(str(e))}</code>", parse_mode="HTML")

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
            
            # Đăng ký handler lắng nghe tin nhắn văn bản (cho báo cáo xe off)
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
            
            # Khởi chạy bot dạng polling
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            # Khởi chạy background loop cho báo cáo cảnh báo hàng ngày
            asyncio.create_task(scheduled_warning_loop(application))
            
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
