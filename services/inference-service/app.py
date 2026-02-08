from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import cv2
import numpy as np
import base64
from ultralytics import YOLO
import uvicorn

app = FastAPI(title="Inference Service", version="1.0.0")

# Load YOLO model at startup
model = None  # downloads on first run

@app.on_event("startup")
async def load_model():
    global model
    print("Loading YOLO model...")
    model = YOLO('yolov8n.pt')  # YOLOv8 nano - fast on CPU
    print("Model loaded successfully!")

class Frame(BaseModel):
    frame_id: int
    data: str  # base64 encoded image

class InferenceRequest(BaseModel):
    frames: List[str]  # List of base64 encoded images

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    class_id: int
    class_name: str
    confidence: float

class FramePrediction(BaseModel):
    frame_idx: int
    boxes: List[BoundingBox]

class InferenceResponse(BaseModel):
    predictions: List[FramePrediction]

@app.get("/")
async def root():
    return {"message": "Inference Service", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/infer", response_model=InferenceResponse)
def infer(request: InferenceRequest):
    """
    Run inference on a batch of frames
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    MAX_FRAMES = 32

    if len(request.frames) > MAX_FRAMES:
        raise HTTPException(status_code=413, detail="Too many frames")

    predictions = []
    
    for idx, frame_b64 in enumerate(request.frames):
        try:
            # Decode base64 to image
            img_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print(f"Failed to decode frame {idx}")
                continue
            
            # Run YOLO inference
            results = model(img, verbose=False)[0]
            
            # Extract bounding boxes
            boxes = []
            if results.boxes is not None:
                for box in results.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    confidence = float(box.conf[0].cpu().numpy())
                    class_name = model.names[class_id]
                    
                    boxes.append(BoundingBox(
                        x1=float(x1),
                        y1=float(y1),
                        x2=float(x2),
                        y2=float(y2),
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence
                    ))
            
            predictions.append(FramePrediction(
                frame_idx=idx,
                boxes=boxes
            ))
            
        except Exception as e:
            print(f"Error processing frame {idx}: {e}")
            predictions.append(FramePrediction(frame_idx=idx, boxes=[]))
    
    return InferenceResponse(predictions=predictions)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)