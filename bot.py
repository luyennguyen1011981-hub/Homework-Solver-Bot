import os
import discord
import io
import re
import socket 
import time   
from PIL import Image
import google.generativeai as genai 
from google.api_core.exceptions import GoogleAPICallError 
from pytesseract import image_to_string 

# =======================================================
# THÊM CƠ CHẾ KIỂM TRA KẾT NỐI MẠNG (FIX LỖI DNS)
# =======================================================
def check_dns_and_wait(host="discord.com", port=443, timeout=5):
    """Kiểm tra kết nối mạng/DNS trước khi bot cố gắng đăng nhập."""
    max_retries = 10
    print("--- BẮT ĐẦU KIỂM TRA KẾT NỐI MẠNG (DNS CHECK) ---")
    for i in range(max_retries):
        try:
            # Cố gắng phân giải tên miền và kết nối
            socket.create_connection((host, port), timeout=timeout)
            print(f"✅ DNS Check: Kết nối tới {host} thành công!")
            return True
        except Exception:
            print(f"❌ DNS Check: Thất bại ({i+1}/{max_retries}). Đang thử lại...")
            time.sleep(min(2 ** i, 60)) 
    
    print("🚨 LỖI NGHIÊM TRỌNG: Quá số lần thử. Không thể kết nối tới Discord.")
    return False

# Chạy kiểm tra mạng trước khi tiếp tục
if not check_dns_and_wait():
    exit(1) 

# =======================================================
# CẤU HÌNH BOT VÀ API
# =======================================================

# Lấy Token và Key từ Biến Môi trường (Secrets)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

if not DISCORD_TOKEN or not GENAI_API_KEY:
    print("🚨 LỖI: Thiếu DISCORD_TOKEN hoặc GENAI_API_KEY. Kiểm tra lại Repository secrets.")
    exit(1)

# Cấu hình Discord Bot
intents = discord.Intents.default()
intents.message_content = True  # Bật quyền đọc nội dung tin nhắn
bot = discord.Client(intents=intents)

# =======================================================
# CẤU HÌNH GEMINI API (ĐÃ SỬA LỖI CLIENT)
# =======================================================
# Sửa lỗi: AttributeError: module 'google.generativeai' has no attribute 'Client'
# Khởi tạo Client và Model Name riêng biệt
client = genai.Client(api_key=GENAI_API_KEY)
model_name = "gemini-2.5-flash" 

# =======================================================
# HÀM XỬ LÝ ẢNH VÀ TRÍCH XUẤT TEXT
# =======================================================
def extract_text_from_image(image: Image.Image):
    """Trích xuất văn bản từ hình ảnh bằng Tesseract OCR."""
    try:
        # Cần đảm bảo Tesseract đã được cài đặt đúng (đã làm trong Dockerfile)
        text = image_to_string(image, lang='vie+eng')
        return text.strip()
    except Exception as e:
        print(f"Lỗi khi trích xuất OCR: {e}")
        return None

# =======================================================
# HÀM GỌI API GEMINI (ĐÃ SỬA LỖI TRUYỀN THAM SỐ MODEL)
# =======================================================
async def generate_response(prompt_text, images=None):
    """Gửi yêu cầu tới Gemini API."""
    contents = []
    
    # 1. Thêm System Instruction (Hướng dẫn cho AI)
    system_instruction = (
        "Bạn là 'Homework Solver Bot', một trợ lý giải bài tập học đường chuyên nghiệp. "
        "Ngôn ngữ phản hồi mặc định là Tiếng Việt. "
        "Hãy luôn giải quyết vấn đề một cách chi tiết, dễ hiểu, từng bước một. "
        "Nếu người dùng gửi ảnh, hãy trích xuất nội dung câu hỏi từ ảnh và đưa ra lời giải. "
        "Nội dung câu hỏi: " + prompt_text
    ) 
    
    config = {"system_instruction": system_instruction}

    # 2. Thêm Hình ảnh (nếu có)
    if images:
        contents.extend(images)
    
    # 3. Thêm Văn bản
    contents.append(prompt_text)

    try:
        # Đã sửa lỗi: Dùng model_name (string) thay vì object 'model' đã lỗi
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
        return response.text
    except GoogleAPICallError as e: 
        return f"🚨 Lỗi API Gemini: Đã xảy ra lỗi khi gọi AI. Lỗi: {e}"
    except Exception as e:
        return f"🚨 Lỗi không xác định: {e}"

# =======================================================
# XỬ LÝ SỰ KIỆN DISCORD
# =======================================================
@bot.event
async def on_ready():
    """Xử lý khi bot đăng nhập thành công."""
    print(f'✅ Bot đã đăng nhập: {bot.user}')
    # Thiết lập trạng thái hoạt động của bot
    activity = discord.Activity(type=discord.ActivityType.listening, name="yêu cầu giải bài | Dùng @bot")
    await bot.change_presence(activity=activity)

@bot.event
async def on_message(message):
    """Xử lý mọi tin nhắn đến."""
    # 1. Bỏ qua tin nhắn của chính bot
    if message.author == bot.user:
        return

    # 2. Kiểm tra có đề cập (@mention) đến bot không
    if bot.user in message.mentions:
        # Xóa @mention khỏi nội dung tin nhắn
        question = re.sub(r'<@!?\d+>', '', message.content).strip()
        
        # Thiết lập phản hồi ban đầu
        response_text = "Không tìm thấy câu hỏi hoặc hình ảnh đính kèm rõ ràng. Vui lòng gửi lại câu hỏi của bạn."
        
        # Lấy file đính kèm
        attachments = message.attachments
        images_to_send = []
        
        # Xử lý hình ảnh nếu có
        if attachments:
            await message.channel.send("🔍 Bot đã nhận được hình ảnh và đang tiến hành xử lý/giải bài...", delete_after=5)
            
            # Tải và chuyển đổi hình ảnh
            try:
                for attachment in attachments:
                    if attachment.content_type and attachment.content_type.startswith('image'):
                        image_bytes = await attachment.read()
                        image = Image.open(io.BytesIO(image_bytes))
                        images_to_send.append(image)
                        
                        # Thử trích xuất văn bản từ ảnh để làm rõ câu hỏi
                        ocr_text = extract_text_from_image(image)
                        if ocr_text:
                            question = f"{question}\n[Văn bản được trích xuất từ ảnh]: {ocr_text}"
                        
            except Exception as e:
                response_text = f"🚨 Lỗi xử lý hình ảnh: Không thể đọc hoặc trích xuất văn bản từ hình ảnh. Lỗi: {e}"
                await message.channel.send(response_text)
                return

        # Chỉ xử lý nếu có câu hỏi (dù là từ text hay OCR)
        if question or images_to_send:
            
            # Gửi tin nhắn tạm thời báo bot đang xử lý
            thinking_msg = await message.channel.send(f"🤖 Bot đang suy nghĩ và tìm lời giải cho:\n> {question[:150]}...")
            
            # Gọi API Gemini
            try:
                response_content = await generate_response(question, images=images_to_send)
                response_text = response_content
            except Exception as e:
                response_text = f"🚨 Lỗi gọi Gemini API: {e}"

            # Xóa tin nhắn "đang suy nghĩ"
            await thinking_msg.delete()
            
            # Cắt nội dung trả lời nếu quá dài (Discord giới hạn 2000 ký tự)
            if len(response_text) > 2000:
                response_text = response_text[:1990] + "..."
            
            # Gửi phản hồi
            await message.channel.send(f"**📖 Lời giải từ Homework Solver Bot:**\n{response_text}", reference=message)

# Khởi động bot
try:
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure:
    print("🚨 LỖI ĐĂNG NHẬP: Token Discord không hợp lệ. Vui lòng kiểm tra lại DISCORD_TOKEN.")
except Exception as e:
    print(f"🚨 LỖI KHÔNG XÁC ĐỊNH: {e}")
