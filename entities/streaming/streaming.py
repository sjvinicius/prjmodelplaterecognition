import os
import time
import uuid
import cv2
import base64
import threading
from collections import deque
from flask import Blueprint, Response
from ultralytics import YOLO
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import numpy as np
import subprocess

load_dotenv()
stream_bp = Blueprint("stream_bp", __name__)

# =========================
# CONFIGURAÇÃO
# =========================
SECRET_KEY = os.getenv("IMAGE_SECRET_KEY", "mysecretkey").encode()
cipher = Fernet(SECRET_KEY)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

DEBUG_CAMERA = os.getenv("DEBUG_CAMERA", "true").lower() == "true"
DEBUG_CAMERA = False
RTSP_URL = os.getenv("RTSP_URL", "rtsp://170.93.143.139/rtplive/470011e600ef003a004ee33696235daa")
LOCAL_VIDEO = os.getenv("LOCAL_VIDEO", "resources/video480p.mp4")

if DEBUG_CAMERA:
    CAMERA_SOURCE = os.path.join(BASE_DIR, LOCAL_VIDEO)
    print("[CAMERA] DEBUG: vídeo local")
else:
    CAMERA_SOURCE = RTSP_URL
    print("[CAMERA] PRODUÇÃO: RTSP")

EVENTS_DIR = os.path.join(BASE_DIR, "events")
os.makedirs(EVENTS_DIR, exist_ok=True)

FRAME_SKIP = 1 if DEBUG_CAMERA else int(os.getenv("FRAME_SKIP", 3))
PLATE_COOLDOWN = int(os.getenv("PLATE_COOLDOWN", 30))
MIN_PLATE_AREA = int(os.getenv("MIN_PLATE_AREA", 3000))
MIN_VEHICLE_AREA = int(os.getenv("MIN_VEHICLE_AREA", 10000))
IOU_MATCH = float(os.getenv("IOU_MATCH", 0.5))
SHOW_BORDER_IDENTIFICATION = os.getenv("SHOW_BORDER_IDENTIFICATION", "true").lower() == "true"

# =========================
# MODELOS
# =========================
VEHICLE_MODEL = YOLO("yolov8n.pt")
PLATE_MODEL = YOLO("models/LP-detection.pt")

# =========================
# ESTADO
# =========================
ACTIVE_PLATES = {}

# =========================
# CLASSE DE CÂMERA
# =========================
class RTSPCamera:
    def __init__(self, url, buffer_size=30, reconnect_delay=2, is_local=False, width=640, height=360):
        self.url = url
        self.buffer = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        self.running = True
        self.last_frame_time = 0
        self.reconnect_delay = reconnect_delay
        self.is_local = is_local
        self.width = width
        self.height = height
        self.proc = None
        self.cap = None
        self.frame_interval = 0.033

        threading.Thread(target=self._reader, daemon=True).start()

    def connect(self):
        # Fecha processo anterior
        if self.proc:
            self.proc.kill()
            self.proc = None
        if self.cap:
            self.cap.release()
            self.cap = None

        if self.is_local:
            self.cap = cv2.VideoCapture(self.url)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.frame_interval = 1 / fps if fps > 0 else 0.033
        else:
            # RTSP via FFmpeg
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", self.url,
                "-f", "rawvideo",
                "-pix_fmt", "bgr24",
                "-"
            ]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10**8)

    def _reader(self):
        self.connect()
        while self.running:
            try:
                if self.is_local:
                    if not self.cap.isOpened():
                        time.sleep(self.reconnect_delay)
                        self.connect()
                        continue
                    ret, frame = self.cap.read()
                    if not ret:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                else:
                    raw_frame = self.proc.stdout.read(self.width * self.height * 3)
                    if len(raw_frame) != self.width * self.height * 3:
                        self.connect()
                        time.sleep(self.reconnect_delay)
                        continue
                    frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((self.height, self.width, 3))
            except Exception as e:
                print("[CAMERA] Erro:", e)
                self.connect()
                time.sleep(self.reconnect_delay)
                continue

            with self.lock:
                self.buffer.append(frame)
                self.last_frame_time = time.time()

            if self.is_local:
                time.sleep(self.frame_interval)

    def read(self):
        with self.lock:
            if self.buffer:
                return True, self.buffer.popleft()
            return False, None

    def watchdog(self, timeout=5):
        if time.time() - self.last_frame_time > timeout:
            print("[WATCHDOG] Reiniciando stream2...")
            self.connect()


camera = RTSPCamera(CAMERA_SOURCE, is_local=DEBUG_CAMERA, width=640, height=360)

# =========================
# FUNÇÃO IOU
# =========================
def iou(a, b):
    xA, yA = max(a[0], b[0]), max(a[1], b[1])
    xB, yB = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0
    areaA = (a[2] - a[0]) * (a[3] - a[1])
    areaB = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(areaA + areaB - inter)

# =========================
# SALVA EVENTO
# =========================
def save_event(frame, bbox):
    x1, y1, x2, y2 = bbox
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return
    event_id = str(uuid.uuid4())
    ts = int(time.time())
    _, buffer = cv2.imencode(".jpg", crop)
    encrypted = cipher.encrypt(base64.b64encode(buffer)).decode()
    with open(os.path.join(EVENTS_DIR, f"{event_id}.json"), "w") as f:
        f.write(f"""{{
            "event_id": "{event_id}",
            "timestamp": {ts},
            "bbox": [{x1},{y1},{x2},{y2}],
            "image_encrypted": "{encrypted}"
        }}""")
    print(f"[EVENT] {event_id}")

# =========================
# LOOP DE STREAM
# =========================
def gen_frames():
    skip = 0
    fps_count = 0
    fps_time = time.time()
    fps = 0
    while True:
        camera.watchdog()
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.01)
            continue

        skip += 1
        if skip < FRAME_SKIP:
            continue
        skip = 0

        now = time.time()

        # FPS
        fps_count += 1
        if now - fps_time >= 1:
            fps = fps_count
            fps_count = 0
            fps_time = now

        # Limpa placas antigas
        for pid in list(ACTIVE_PLATES):
            p = ACTIVE_PLATES[pid]
            if p["status"] == "sent" and now - p["last_seen"] > PLATE_COOLDOWN * 2:
                del ACTIVE_PLATES[pid]

        # Detecta veículos
        vres = VEHICLE_MODEL(frame, conf=0.6, imgsz=640, verbose=False)[0]

        for b in vres.boxes:
            if int(b.cls[0]) not in [2, 3]:
                continue
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            if (x2 - x1) * (y2 - y1) < MIN_VEHICLE_AREA:
                continue
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            # Detecta placa
            pres = PLATE_MODEL(roi, conf=0.3, imgsz=320, verbose=False)[0]
            for pb in pres.boxes:
                px1, py1, px2, py2 = map(int, pb.xyxy[0])
                ax1, ay1, ax2, ay2 = x1 + px1, y1 + py1, x1 + px2, y1 + py2
                if (ax2 - ax1) * (ay2 - ay1) < MIN_PLATE_AREA:
                    continue

                pid = None
                for k, v in ACTIVE_PLATES.items():
                    if iou(v["bbox"], (ax1, ay1, ax2, ay2)) > IOU_MATCH:
                        pid = k
                        break

                if pid:
                    ACTIVE_PLATES[pid]["last_seen"] = now
                    if now - ACTIVE_PLATES[pid]["last_event"] < PLATE_COOLDOWN:
                        continue
                else:
                    pid = str(uuid.uuid4())
                    ACTIVE_PLATES[pid] = {
                        "bbox": (ax1, ay1, ax2, ay2),
                        "last_seen": now,
                        "last_event": 0,
                        "status": "new"
                    }

                save_event(frame, (ax1, ay1, ax2, ay2))
                ACTIVE_PLATES[pid]["last_event"] = now
                ACTIVE_PLATES[pid]["status"] = "sent"

                if SHOW_BORDER_IDENTIFICATION:
                    cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (0, 255, 0), 2)

        # Exibe FPS
        cv2.putText(frame, f"FPS: {fps}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        ret, buf = cv2.imencode(".jpg", frame)
        yield b"--frame\r\nContent-Type:image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

# =========================
# ROTAS
# =========================
@stream_bp.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@stream_bp.route("/health")
def health():
    now = time.time()
    camera_ok = camera.cap is not None and camera.cap.isOpened()
    frame_ok = now - camera.last_frame_time < 5
    queue_size = len(os.listdir(EVENTS_DIR))
    disk_ok = os.access(EVENTS_DIR, os.W_OK)

    status = {
        "camera_connected": camera_ok,
        "last_frame_seconds": round(now - camera.last_frame_time, 2),
        "stream_alive": frame_ok,
        "queue_size": queue_size,
        "disk_writable": disk_ok,
        "debug_camera": DEBUG_CAMERA
    }

    http_status = 200 if camera_ok and frame_ok and disk_ok else 503
    return status, http_status
