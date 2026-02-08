import cv2
import base64
import json
import time
from kafka import KafkaProducer
import os
import logging
import signal
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RTSP_URL = os.getenv('RTSP_URL', 'rtsp://localhost:8554/demo')
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'video-frames')
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 25))
FPS = int(os.getenv("FPS", 30))

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|timeout;5000000"

class FramePublisher:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            max_request_size=15728640,
            compression_type='gzip',
            linger_ms=10,
            security_protocol='SSL',
            ssl_check_hostname=False,
            ssl_cafile='/etc/ssl/certs/ca-certificates.crt'
        )
        logger.info(f"Kafka Producer initialized: {KAFKA_BOOTSTRAP}")
    
    def connect_stream(self):
        """Connect to RTSP stream with TCP transport."""
        while True:
            cap = cv2.VideoCapture(
                RTSP_URL + "?_rtsp_transport=tcp",
                cv2.CAP_FFMPEG
            )
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
            
            if cap.isOpened():
                logger.info(f"Connected to RTSP stream: {RTSP_URL}")
                return cap
                
            logger.warning("Failed to connect, retrying in 5 seconds...")
            time.sleep(5)
    
    def encode_frame(self, frame):
        """Encode frame to base64 JPEG"""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return base64.b64encode(buffer).decode('utf-8')
    
    def run(self):
        cap = self.connect_stream()
        frame_batch = []
        frame_count = 0
        batch_id = 0
        
        frame_time = 1.0 / FPS
        
        logger.info("Starting frame publishing...")
        
        while True:
            start_time = time.time()
            
            ret, frame = cap.read()
            
            if not ret:
                logger.warning("Stream ended or error, reconnecting...")
                cap.release()
                time.sleep(5)
                cap = self.connect_stream()
                continue
            
            # Encode and add to batch
            frame_b64 = self.encode_frame(frame)
            frame_batch.append({
                "width": frame.shape[1],
                "height": frame.shape[0],
                "encoding": "jpeg",
                "frame_id": frame_count,
                "timestamp": time.time(),
                "data": frame_b64
            })
            
            frame_count += 1
            
            # Send batch when we have 25 frames
            if len(frame_batch) >= BATCH_SIZE:
                message = {
                    "batch_id": batch_id,
                    "frame_count": len(frame_batch),
                    "frames": frame_batch
                }
                
                try:
                    key = str(batch_id).encode()
                    future = self.producer.send(KAFKA_TOPIC, key=key, value=message)
                    future.get(timeout=10)
                    logger.info(f"Sent batch {batch_id} ({len(frame_batch)} frames)")
                    batch_id += 1
                except Exception as e:
                    logger.error(f"Failed to send batch: {e}")
                
                frame_batch = []
            
            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)
    
def shutdown(sig, frame):
    logger.info("Shutting down producer...")
    if publisher:
        publisher.producer.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

if __name__ == '__main__':
    publisher = FramePublisher()
    publisher.run()