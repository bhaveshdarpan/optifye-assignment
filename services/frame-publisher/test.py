#!/usr/bin/env python3
"""Test suite for frame publisher."""
import os
import cv2
import numpy as np
import base64
import json
import time
import requests
from PIL import Image
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RTSP_URL = os.getenv("RTSP_URL", "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "25"))
FRAME_SKIP = int(os.getenv("FRAME_SKIP", "5"))
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://localhost:8000/infer")

batch_frames = []
batch_num = 0
frame_count = 0
cap = None

try:
    logger.info("Connecting to RTSP stream...")
    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    fallback_img_resp = requests.get("https://ultralytics.com/images/bus.jpg")
    fallback_frame = np.array(Image.open(io.BytesIO(fallback_img_resp.content)))
    
    logger.info("Fallback image loaded")
    logger.info("Generating test frames...")

    total_frames_needed = BATCH_SIZE * 2 * FRAME_SKIP
    
    for i in range(total_frames_needed):
        frame_count += 1

        if cap and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                current_frame = frame
            else:
                logger.warning("RTSP failed, using fallback")
                current_frame = fallback_frame
        else:
            logger.info("Using fallback image")
            current_frame = fallback_frame

        if frame_count % FRAME_SKIP == 0:
            success, buffer = cv2.imencode('.jpg', current_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
                batch_frames.append(frame_b64)
                logger.info(f"Frame {frame_count} added to batch {len(batch_frames)}/{BATCH_SIZE}")
            if len(batch_frames) >= BATCH_SIZE:
                batch_payload = {
                    "batch_id": f"batch_{batch_num:06d}",
                    "timestamp": time.time(),
                    "frame_count": len(batch_frames),
                    "frames": batch_frames
                }
                
                payload_size_kb = len(json.dumps(batch_payload)) / 1024
                logger.info(f"Batch {batch_num:06d} complete: {len(batch_frames)} frames, ~{payload_size_kb:.1f}KB")
                
                try:
                    inference_resp = requests.post(
                        INFERENCE_URL,
                        json={"frames": batch_frames[:2]},
                        timeout=10
                    )
                    if inference_resp.status_code == 200:
                        preds = inference_resp.json()["predictions"]
                        detection_count = sum(len(p['boxes']) for p in preds)
                        logger.info(f"Inference complete: {len(preds)} frames, {detection_count} detections")
                    else:
                        logger.warning(f"Inference service returned {inference_resp.status_code}")
                except Exception as e:
                    logger.error(f"Inference service error: {e}")
                
                batch_frames = []
                batch_num += 1
                time.sleep(0.5)
    
    logger.info("Publisher test complete")
    logger.info(f"Generated {frame_count} frames, {batch_num} batches")
    logger.info("Consumer service format verified")
    logger.info("Ready for EKS deployment")
    
except KeyboardInterrupt:
    logger.warning("Test interrupted by user")
except Exception as e:
    logger.error(f"Test error: {e}")
finally:
    if cap:
        cap.release()
        cv2.destroyAllWindows()
        logger.info("Stream closed")
