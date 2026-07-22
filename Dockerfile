FROM python:3.11-slim

WORKDIR /app

# Chỉ copy file cần thiết để build nhanh hơn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Chromium và các thư viện hệ thống cần thiết cho Playwright
RUN playwright install --with-deps chromium

# Copy source code chính (dùng wildcard để không sập build nếu upload thiếu file phụ)
COPY main.py .
COPY telegram_bot.p[y] .
COPY giao_hang_scheduler.p[y] .
COPY collect_money_bot.p[y] .
COPY collect_money_scheduler.p[y] .
COPY vanhanh_bot.p[y] .
COPY vanhanh_scheduler.p[y] .
COPY odo_monitor.p[y] .
COPY telegram_odo.p[y] .
COPY odo_scheduler.p[y] .
COPY app.j[s] .
COPY index.htm[l] .
COPY styles.cs[s] .
COPY ghn_logo.pn[g] .
COPY Procfil[e] .
RUN mkdir -p /app/scratch
COPY alien-oarlock-499610-a5-2d813b6cc71d.jso[n] .

# Runtime env vars được Railway inject tự động — không cần hardcode gì ở đây
EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
