FROM python:3.11-slim

WORKDIR /app

# Chỉ copy file cần thiết để build nhanh hơn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Chromium và các thư viện hệ thống cần thiết cho Playwright
RUN playwright install --with-deps chromium

# Copy source code chính
COPY main.py .
COPY telegram_bot.py .
COPY giao_hang_scheduler.py .
COPY collect_money_bot.py .
COPY collect_money_scheduler.py .
COPY vanhanh_bot.py .
COPY vanhanh_scheduler.py .
COPY app.js .
COPY index.html .
COPY styles.css .
COPY ghn_logo.png .
COPY Procfile .
RUN mkdir -p /app/scratch
COPY alien-oarlock-499610-a5-2d813b6cc71d.jso[n] .


# Runtime env vars được Railway inject tự động — không cần hardcode gì ở đây
EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
