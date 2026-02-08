import json
import base64
import os
import ssl
import signal
import sys
import httpx
import cv2
import numpy as np
from kafka import KafkaConsumer
import boto3
from datetime import datetime
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'video-frames')
KAFKA_CONSUMER_GROUP = os.getenv('KAFKA_CONSUMER_GROUP', 'inference-consumer-group')
INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://inference-service:8000')
S3_BUCKET = os.getenv('S3_BUCKET')
AWS_REGION = os.getenv('AWS_REGION', '')

def _check_required():
    missing = []
    if not (KAFKA_BOOTSTRAP or '').strip():
        missing.append('KAFKA_BOOTSTRAP')
    if not (S3_BUCKET or '').strip():
        missing.append('S3_BUCKET')
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

_REGION = (AWS_REGION or '').strip() or 'us-east-1'
s3_client = boto3.client('s3', region_name=_REGION)
HTTP_TIMEOUT = float(os.getenv('INFERENCE_HTTP_TIMEOUT', '120.0'))
http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

class Colors:
    """Color palette for bounding box rendering."""
    COLORS = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 255), (0, 255, 255),
        (128, 0, 0), (0, 128, 0), (0, 0, 128)
    ]
    
    @classmethod
    def get_color(cls, class_id):
        return cls.COLORS[class_id % len(cls.COLORS)]

def draw_boxes(image, predictions):
    """Draw bounding boxes with labels on image"""
    if not predictions or len(predictions) == 0:
        return image
    
    pred = predictions[0]
    boxes = pred.get('boxes', [])
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.5))
    
    for box in boxes:
        if box['confidence'] > CONFIDENCE_THRESHOLD:
            x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x2']), int(box['y2'])
            class_name = box['class_name']
            confidence = box['confidence']
            class_id = box['class_id']
            
            color = Colors.get_color(class_id)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name}: {confidence:.2f}"
            (label_width, label_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
            )
            cv2.rectangle(
                image, 
                (x1, y1 - label_height - 10), 
                (x1 + label_width, y1), 
                color, 
                -1
            )
            cv2.putText(
                image,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )
    
    return image

async def call_inference_service(frames_b64):
    for attempt in range(3):
        try:
            response = await http_client.post(
                f"{INFERENCE_URL}/infer",
                json={"frames": frames_b64}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)


async def process_batch_async(batch_data):
    """Process a batch of frames"""
    frames = batch_data['frames']
    batch_id = batch_data['batch_id']
    
    logger.info(f"Processing batch {batch_id} with {len(frames)} frames")
    
    try:
        frame_b64_list = [f['data'] for f in frames]
        result = await call_inference_service(frame_b64_list)
        predictions = result['predictions']
        
        logger.info(f"Received {len(predictions)} predictions for batch {batch_id}")
        
        first_frame_b64 = frames[0]['data']
        img_bytes = base64.b64decode(first_frame_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("Failed to decode image")
            return
        
        annotated_img = draw_boxes(img, predictions)
        _, buffer = cv2.imencode('.jpg', annotated_img)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f"annotated/batch_{batch_id:06d}_{timestamp}.jpg"
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=buffer.tobytes(),
                ContentType='image/jpeg',
                Metadata={
                    'batch_id': str(batch_id),
                    'frame_count': str(len(frames)),
                    'detections': str(len(predictions[0].get('boxes', [])))
                }
            )
        except Exception:
            logger.error("S3 upload failed")
            raise

        logger.info(
            "processing_batch",
            extra={"batch_id": batch_id, "frame_count": len(frames)}
        )

        
    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {e}", exc_info=True)


def main():
    _check_required()
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP.split(','),
        group_id=KAFKA_CONSUMER_GROUP,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        security_protocol="SSL",
        ssl_context=ssl_context,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        max_poll_records=1
    )

    logger.info(f"Consumer started, listening to {KAFKA_TOPIC}")
    logger.info(f"Inference service: {INFERENCE_URL}")
    logger.info(f"S3 bucket: {S3_BUCKET}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    shutdown_requested = False

    def shutdown(sig=None, frame=None):
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("Shutdown requested, finishing current batch then exiting...")

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        for message in consumer:
            if shutdown_requested:
                break
            try:
                batch_data = message.value
                loop.run_until_complete(process_batch_async(batch_data))
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        logger.info("Closing consumer and HTTP client...")
        loop.run_until_complete(http_client.aclose())
        consumer.close()
        loop.close()


if __name__ == '__main__':
    main()
    sys.exit(0)