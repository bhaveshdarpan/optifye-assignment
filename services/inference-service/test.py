import requests
import base64
import json
from typing import List
from PIL import Image
import io

def test_yolo_inference():
    """Test your exact /infer endpoint with base64 frames"""
    
    print("🧪 Testing YOLOv8 Inference Service...")
    print("Endpoint: http://localhost:8000/infer")
    print("-" * 50)
    
    # Test 1: Health check
    print("1. Health check...")
    health_resp = requests.get("http://localhost:8000/health")
    print(f"   Status: {health_resp.status_code}")
    if health_resp.status_code == 200:
        print(f"   Response: {health_resp.json()}")
    
    # Test 2: Download test image
    print("\n2. Downloading test image...")
    img_url = "https://ultralytics.com/images/bus.jpg"
    img_resp = requests.get(img_url)
    img = Image.open(io.BytesIO(img_resp.content))
    print(f"   Image: {img.size} ({img.mode})")
    
    # Test 3: Convert to base64 (exact format your API expects)
    print("\n3. Converting to base64...")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    img_bytes = buffer.getvalue()
    frame_b64 = base64.b64encode(img_bytes).decode('utf-8')
    print(f"   Frame size: {len(img_bytes)} bytes")
    
    # Test 4: Single frame inference (matches your API exactly)
    print("\n4. Testing /infer endpoint...")
    payload = {
        "frames": [frame_b64]
    }
    
    resp = requests.post(
        "http://localhost:8000/infer",
        json=payload
    )
    
    print(f"   Status: {resp.status_code}")
    
    if resp.status_code == 200:
        result = resp.json()
        print("\n✅ SUCCESS! YOLO detections:")
        print(json.dumps(result, indent=2))
        
        # Parse results
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
                    for box in boxes[:3]:  # Show first 3
                        print(f"     - {box['class_name']}: {box['confidence']:.2f}")
        else:
            print("   ⚠️  No detections found")
    else:
        print(f"   ❌ Error: {resp.text}")
    
    return resp.status_code == 200

if __name__ == "__main__":
    success = test_yolo_inference()
    print("\n" + ("🎉 PIPELINE READY FOR EKS!" if success else "❌ Fix inference service first"))
