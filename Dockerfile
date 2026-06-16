FROM python:3.11-slim

WORKDIR /app

# Chỉ copy file cần thiết để build nhanh hơn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code chính
COPY main.py .
COPY telegram_bot.py .
COPY giao_hang_scheduler.py .
COPY collect_money_bot.py .
COPY collect_money_scheduler.py .
COPY app.js .
COPY index.html .
COPY styles.css .
COPY Procfile .


# Runtime env vars được Railway inject tự động — không cần hardcode gì ở đây
EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
