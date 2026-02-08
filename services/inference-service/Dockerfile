FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

# Add non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
# Reduce workers to 1 (YOLO CPU is single-threaded bottleneck)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
