FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and ONNX
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Add onnxruntime to your requirements.txt
RUN pip install --no-cache-dir -r requirements.txt onnxruntime onnxscript

# Export the model to ONNX format during build
# This avoids all PyTorch 2.6+ "Weights only load failed" errors
RUN python3 -c "\
import torch; \
# Monkey-patch torch.load to revert to pre-2.6 behavior \
orig_load = torch.load; \
torch.load = lambda *args, **kwargs: orig_load(*args, **kwargs, weights_only=False); \
from ultralytics import YOLO; \
model = YOLO('yolov8n.pt'); \
model.export(format='onnx')"

COPY app.py .

EXPOSE 8000

# Add non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
