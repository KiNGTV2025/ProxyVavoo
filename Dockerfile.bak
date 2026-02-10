FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 7860

CMD ["gunicorn", "app:app", \
     "--worker-class", "gevent", \
     "--workers", "6", \
     "--worker-connections", "2000", \
     "--bind", "0.0.0.0:7860", \
     "--timeout", "240", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "15000", \
     "--max-requests-jitter", "1500", \
     "--worker-tmp-dir", "/dev/shm", \
     "--limit-request-line", "8190", \
     "--limit-request-field_size", "8190", \
     "--preload", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "warning"]