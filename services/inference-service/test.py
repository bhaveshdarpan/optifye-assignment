import os
import requests
import base64
import json
from typing import List
from PIL import Image
import io

INFERENCE_BASE = os.getenv("INFERENCE_URL", "http://localhost:8000").rstrip("/")
HEALTH_URL = f"{INFERENCE_BASE}/health"
INFER_URL = f"{INFERENCE_BASE}/infer"

def test_yolo_inference():
    """Test your exact /infer endpoint with base64 frames"""
    
    print("🧪 Testing YOLOv8 Inference Service...")
    print(f"Endpoint: {INFER_URL}")
    print("-" * 50)

    print("1. Health check...")
    health_resp = requests.get(HEALTH_URL)
    print(f"   Status: {health_resp.status_code}")
    if health_resp.status_code == 200:
        print(f"   Response: {health_resp.json()}")
    
    print("\n2. Downloading test image...")
    img_url = "https://ultralytics.com/images/bus.jpg"
    img_resp = requests.get(img_url)
    img = Image.open(io.BytesIO(img_resp.content))
    print(f"   Image: {img.size} ({img.mode})")
    
    print("\n3. Converting to base64...")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    img_bytes = buffer.getvalue()
    frame_b64 = base64.b64encode(img_bytes).decode('utf-8')
    print(f"   Frame size: {len(img_bytes)} bytes")
    
    print("\n4. Testing /infer endpoint...")
    payload = {
        "frames": [frame_b64]
    }
    
    resp = requests.post(INFER_URL, json=payload)
    
    print(f"   Status: {resp.status_code}")
    
    if resp.status_code == 200:
        result = resp.json()
        print("\n✅ SUCCESS! YOLO detections:")
        print(json.dumps(result, indent=2))

        predictions = result.get("predictions", [])
        if predictions:
            first_frame = predictions[0]
            print(f"\n📊 Summary:")
            print(f"   Frames processed: {len(predictions)}")
            print(f"   Total detections: {sum(len(f['boxes']) for f in predictions)}")
            for frame in predictions:
                boxes = frame['boxes']
                if boxes:
                    print(f"   Frame {frame['frame_idx']}: {len(boxes)} objects")
                    for box in boxes[:3]:
                        print(f"     - {box['class_name']}: {box['confidence']:.2f}")
        else:
            print("   ⚠️  No detections found")
    else:
        print(f"   ❌ Error: {resp.text}")
    
    return resp.status_code == 200

if __name__ == "__main__":
    success = test_yolo_inference()
    print("\n" + ("🎉 PIPELINE READY FOR EKS!" if success else "❌ Fix inference service first"))
