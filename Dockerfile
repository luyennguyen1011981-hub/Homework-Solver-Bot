# Base image with Python 3.11 and Debian Bullseye
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies (for tesseract OCR)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    # Dependencies for Pillow/other libs
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    # Cleaning up apt cache to save space
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot.py .

# Command to run the bot
CMD ["python", "bot.py"]

