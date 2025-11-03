# Dùng base image Python 3.11 nhẹ
FROM python:3.11-slim

# Cài đặt Tesseract và các gói ngôn ngữ cần thiết (vie/eng)
# BƯỚC QUAN TRỌNG NHẤT: Cài đặt chương trình hệ thống Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép và cài đặt Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép bot.py và chạy
COPY bot.py .

# Thiết lập biến môi trường để bot.py biết Tesseract ở đâu trên Linux
ENV TESSERACT_CMD="/usr/bin/tesseract"

# Lệnh chạy bot
CMD ["python", "bot.py"]