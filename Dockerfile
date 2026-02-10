FROM python:3.12-slim

WORKDIR /app

# requirements önce kopyalanır (cache avantajı)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# app dosyası
COPY app.py .

EXPOSE 7860

CMD ["gunicorn", "app:app",
     "--worker-class", "gevent",
     "--workers", "2",
     "--worker-connections", "1000",
     "--bind", "0.0.0.0:7860",
     "--timeout", "120",
     "--graceful-timeout", "20",
     "--keep-alive", "5",
     "--max-requests", "5000",
     "--max-requests-jitter", "500",
     "--worker-tmp-dir", "/dev/shm",
     "--preload",
     "--access-logfile", "-",
     "--error-logfile", "-",
     "--log-level", "warning"]