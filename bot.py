import discord
from discord.ext import commands
import google.generativeai as genai
from PIL import Image
import pytesseract
import io
import textwrap
import asyncio
import os # Dùng để quản lý biến môi trường trên server/local

# =========================================================================================
# 🔥 CẤU HÌNH BOT (Sử dụng biến môi trường là tốt nhất cho 24/7)
# =========================================================================================

# 🔑 API key Gemini: Lấy từ biến môi trường, nếu không có thì dùng placeholder
GENAI_API_KEY = os.environ.get("GENAI_API_KEY", "AIzaSyD58IRnq78rebxjOnyXMkBzFgrDJbkBPnM")
genai.configure(api_key=GENAI_API_KEY)

# 🔥 Token Discord: Lấy từ biến môi trường, nếu không có thì mặc định là chuỗi rỗng
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# ⚙️ Cấu hình Bot Discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 🖼 Đường dẫn Tesseract: Quan trọng cho môi trường 24/7 (Linux)
# Server sẽ set biến TESSERACT_CMD thành /usr/bin/tesseract
TESSERACT_PATH = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
except Exception as e:
    # Bỏ qua lỗi nếu Tesseract không cài đặt cục bộ (khi chạy trên server)
    print(f"⚠️ Cảnh báo: Không thể thiết lập Tesseract CMD. Lỗi: {e}")


# =========================================================================================
# 🛠️ CÁC HÀM HỖ TRỢ (Sync & Async)
# =========================================================================================

# Hàm gửi message dài >2000 ký tự (Async)
async def send_long_message(channel, content, reply_to=None):
    chunks = textwrap.wrap(content, 1900, replace_whitespace=False)
    for chunk in chunks:
        if reply_to:
            await channel.send(chunk, reference=reply_to)
        else:
            await channel.send(chunk)

# Hàm đồng bộ (sync) để chạy Tesseract OCR (BLOCKING I/O)
def run_ocr_sync(image):
    # Đảm bảo Tesseract_cmd được set, nếu không sẽ lỗi
    return pytesseract.image_to_string(image, lang="vie+eng").strip()

# Hàm đồng bộ (sync) để gọi API Gemini (BLOCKING I/O)
def generate_content_sync(prompt):
    model = genai.GenerativeModel("gemini-2.5-flash")
    return model.generate_content(prompt)

# =========================================================================================
# 🟢 XỬ LÝ SỰ KIỆN (Events)
# =========================================================================================

# Bot đăng nhập thành công
@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập: {bot.user}")
    print(f"🔥 Bot đang sử dụng Tesseract CMD: {pytesseract.pytesseract.tesseract_cmd}")


# Tự động giải bài khi có ảnh
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Xử lý lệnh (commands) trước
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message) 
        return

    # Xử lý attachment (ảnh)
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
                
                # Bắt đầu xử lý
                await message.channel.send("⏳ Đang xử lý ảnh và gọi AI. Chờ tao xíu...", reference=message)

                try:
                    img_bytes = await attachment.read()
                    image = Image.open(io.BytesIO(img_bytes))

                    # 🔍 OCR - CHẠY BẤT ĐỒNG BỘ TRONG LUỒNG RIÊNG (Fix Heartbeat Block)
                    text = await asyncio.to_thread(run_ocr_sync, image)
                    
                    if not text:
                        await message.reply("⚠️ Không đọc được chữ trong ảnh.")
                        continue

                    # 🤖 Gọi API Gemini - CHẠY BẤT ĐỒNG BỘ TRONG LUỒNG RIÊNG (Fix Heartbeat Block)
                    response = await asyncio.to_thread(
                        generate_content_sync,
                        f"Giải chi tiết bài tập sau đây bằng tiếng Việt:\n{text}"
                    )

                    # 💬 Gửi message
                    await send_long_message(
                        message.channel, 
                        f"**📖 Bài trong ảnh (Đã đọc được):**\n```\n{text}```\n\n**🧠 Lời giải:**\n{response.text}", 
                        reply_to=message
                    )
                
                except Exception as e:
                    print(f"Lỗi khi xử lý ảnh hoặc gọi API: {e}")
                    await message.reply("❌ Xảy ra lỗi trong quá trình xử lý hoặc kết nối AI. Mày kiểm tra lại log.")

# =========================================================================================
# 📚 LỆNH THỦ CÔNG (!giai) - HỖ TRỢ CẢ VĂN BẢN VÀ ẢNH
# =========================================================================================

@bot.command()
async def giai(ctx, *question): 
    
    # 1. Xử lý câu hỏi văn bản (Ưu tiên)
    if question:
        text = " ".join(question).strip()
        
        if text:
            await ctx.send("⏳ Đang gọi AI để giải bài tập văn bản. Chờ tao xíu...")
            try:
                # Gọi API Gemini - BẤT ĐỒNG BỘ
                response = await asyncio.to_thread(
                    generate_content_sync,
                    f"Giải chi tiết bài tập sau đây bằng tiếng Việt:\n{text}"
                )
                
                await send_long_message(
                    ctx.channel, 
                    f"**📖 Bài tập:**\n```\n{text}```\n\n**🧠 Lời giải:**\n{response.text}"
                )
                return # Thoát khỏi hàm nếu đã giải bằng text
                
            except Exception as e:
                print(f"Lỗi khi gọi API Google với văn bản: {e}")
                await ctx.send("❌ Xảy ra lỗi khi kết nối AI để giải bài văn bản.")
                return

    # 2. Xử lý ảnh (Chỉ chạy nếu không có văn bản và có file đính kèm)
    if len(ctx.message.attachments) == 0:
        await ctx.send("📸 Gửi hình bài tập kèm theo lệnh `!giai` hoặc nhập câu hỏi sau `!giai` đi bro 😎")
        return

    # Gửi tin nhắn thông báo đang xử lý ảnh
    await ctx.send("⏳ Đang xử lý ảnh và gọi AI. Chờ tao xíu...")

    # Xử lý các file đính kèm
    for attachment in ctx.message.attachments:
        try:
            img_bytes = await attachment.read()
            image = Image.open(io.BytesIO(img_bytes))
            
            # OCR - BẤT ĐỒNG BỘ
            text_from_image = await asyncio.to_thread(run_ocr_sync, image)
            
            if not text_from_image:
                await ctx.send("⚠️ Không đọc được chữ trong ảnh.")
                continue

            # Gọi API Gemini - BẤT ĐỒNG BỘ
            response = await asyncio.to_thread(
                generate_content_sync,
                f"Giải chi tiết bài tập sau đây bằng tiếng Việt:\n{text_from_image}"
            )

            await send_long_message(
                ctx.channel, 
                f"**📖 Bài trong ảnh (Đã đọc được):**\n```\n{text_from_image}```\n\n**🧠 Lời giải:**\n{response.text}"
            )
            
        except Exception as e:
            print(f"Lỗi khi xử lý ảnh hoặc gọi API: {e}")
            await ctx.send("❌ Xảy ra lỗi trong quá trình xử lý hoặc kết nối AI.")

# =========================================================================================
# 🔥 CHẠY BOT
# =========================================================================================

if __name__ == "__main__":
    # KIỂM TRA ĐỘ SẠCH SẼ (Chỉ cần kiểm tra xem có token không)
    if not DISCORD_TOKEN:
        print("\n\n🚨 LỖI: CHƯA CUNG CẤP DISCORD TOKEN THẬT!")
        print("Vui lòng thiết lập biến môi trường DISCORD_TOKEN và GENAI_API_KEY trên Railway.\n")
        exit() 
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"\n\n🚨 LỖI NGHIÊM TRỌNG KHI KHỞI ĐỘNG BOT: {e}")
        print("Kiểm tra lại DISCORD_TOKEN và INTENTS (Đã bật hết chưa?).")

