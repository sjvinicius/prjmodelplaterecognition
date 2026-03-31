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
from paddleocr import PaddleOCR
from collections import Counter
from entities.security.whitelist import load_whitelist_cached

load_dotenv()
stream_bp = Blueprint("stream_bp", __name__)

# =========================
# CONFIGURAÇÃO
# =========================
SECRET_KEY = os.getenv("IMAGE_SECRET_KEY", "mysecretkey").encode()
cipher = Fernet(SECRET_KEY)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

DEBUG_CAMERA = os.getenv("DEBUG_CAMERA", "true").lower() == "true"
CAMERA_SOURCE_ENV = os.getenv("CAMERA_SOURCE", "resources/video480p.mp4")

EVENTS_DIR = os.path.join(BASE_DIR, "events")
os.makedirs(EVENTS_DIR, exist_ok=True)

FRAME_SKIP = 1 if DEBUG_CAMERA else int(os.getenv("FRAME_SKIP", 3))
PLATE_COOLDOWN = int(os.getenv("PLATE_COOLDOWN", 30))
MIN_PLATE_AREA = int(os.getenv("MIN_PLATE_AREA", 3000))
MIN_VEHICLE_AREA = int(os.getenv("MIN_VEHICLE_AREA", 10000))
IOU_MATCH = float(os.getenv("IOU_MATCH", 0.5))
SHOW_BORDER_IDENTIFICATION = os.getenv("SHOW_BORDER_IDENTIFICATION", "true").lower() == "true"

OCR_ENABLED = True
OCR_MIN_CONFIDENCE = 0.6
CONFIRMATION_THRESHOLD = 3
OCR_FRAME_SKIP = 2

# =========================
# MODELOS
# =========================
VEHICLE_MODEL = YOLO("models/yolov8n.pt")
PLATE_MODEL = YOLO("models/LP-detection.pt")

# =========================
# ESTADO
# =========================
ACTIVE_PLATES = {}
_camera_instance = None  # singleton da câmera

ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en'
)

def normalize_plate(text):
    return text.replace("-", "").replace(" ", "").upper()


def read_plate_ocr(crop):
    result = ocr.ocr(crop)

    if not result or not result[0]:
        return None

    best_text = None
    best_conf = 0

    for line in result[0]:
        text = line[1][0]
        conf = line[1][1]

        if conf > best_conf:
            best_text = text
            best_conf = conf

    if best_text and best_conf > OCR_MIN_CONFIDENCE:
        return normalize_plate(best_text)

    return None


def most_common(lst):
    return Counter(lst).most_common(1)[0][0]

def trigger_gate():
    print("[GATE] ABRINDO PORTÃO 🚪")
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
def save_event(frame, bbox, pid):
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
            "plate_id": "{pid}",
            "event_id": "{event_id}",
            "timestamp": {ts},
            "bbox": [{x1},{y1},{x2},{y2}],
            "image_encrypted": "{encrypted}"
        }}""")
    print(f"[EVENT] {event_id}")

# =========================
# CLASSE DE CÂMERA
# =========================
# =========================
# CLASSE DE CÂMERA AJUSTADA
# =========================
class CameraSource:
    def __init__(self, source, buffer_size=30, reconnect_delay=5, width=640, height=360):
        self.source = source
        self.buffer = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        self.running = True
        self.last_frame_time = 0
        self.reconnect_delay = reconnect_delay
        self.width = width
        self.height = height

        self.proc = None
        self.cap = None
        self.frame_interval = 0.033

        self.is_local_file = os.path.isfile(source)
        self.is_webcam = isinstance(source, int)
        self.is_rtsp = isinstance(source, str) and source.startswith("rtsp://")

        threading.Thread(target=self._reader, daemon=True).start()

    # =========================
    # LOG DO FFMPEG
    # =========================
    def _log_ffmpeg(self):
        for line in self.proc.stderr:
            print("[FFMPEG]", line.decode(errors="ignore").strip())

    # =========================
    # LEITURA SEGURA
    # =========================
    def read_exact(self, size):
        data = b''
        while len(data) < size:
            packet = self.proc.stdout.read(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    # =========================
    # CONEXÃO
    # =========================
    def connect(self):
        print("[CAMERA] Reiniciando conexão...")

        if self.proc:
            self.proc.kill()
            self.proc = None

        if self.cap:
            self.cap.release()
            self.cap = None

        time.sleep(2)

        # =========================
        # RTSP (FFMPEG ESTÁVEL)
        # =========================
        if self.is_rtsp:
            print(f"[CAMERA] Conectando RTSP: {self.source}")

            # binffmpeg = r"C:\Users\Vinicius\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-essentials_build\bin\ffmpeg.exe"
            binffmpeg = "ffmpeg"  # assume ffmpeg no PATH
            self.proc = subprocess.Popen(
                [
                    binffmpeg,
                    "-rtsp_transport", "udp",
                    "-timeout", "5000000",
                    "-i", self.source,
                    "-an",
                    "-vf", f"scale={self.width}:{self.height}:flags=fast_bilinear",
                    "-pix_fmt", "bgr24",
                    "-f", "rawvideo",
                    "-"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**7
            )

            threading.Thread(target=self._log_ffmpeg, daemon=True).start()

            self.frame_interval = 0.033
            return

        # =========================
        # WEBCAM / ARQUIVO
        # =========================
        if self.is_local_file or self.is_webcam:
            while True:
                self.cap = cv2.VideoCapture(self.source)

                if self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        with self.lock:
                            self.buffer.append(frame)
                            self.last_frame_time = time.time()

                        fps = self.cap.get(cv2.CAP_PROP_FPS)
                        self.frame_interval = 1 / fps if fps > 0 else 0.033

                        print(f"[CAMERA] Conectado: {self.source}")
                        return

                print("[CAMERA] Tentando reconectar webcam/video...")
                time.sleep(2)

    # =========================
    # THREAD DE LEITURA
    # =========================
    def _reader(self):
        self.connect()

        while self.running:
            try:
                # =========================
                # WEBCAM / ARQUIVO
                # =========================
                if self.is_local_file or self.is_webcam:
                    if not self.cap or not self.cap.isOpened():
                        self.connect()
                        continue

                    ret, frame = self.cap.read()

                    if not ret:
                        if self.is_local_file:
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        else:
                            self.connect()
                            continue

                # =========================
                # RTSP (RAWVIDEO ESTÁVEL)
                # =========================
                else:
                    if not self.proc:
                        self.connect()
                        continue

                    frame_size = self.width * self.height * 3
                    raw = self.read_exact(frame_size)

                    if raw is None:
                        print("[RTSP] Falha ao ler frame, reconectando...")
                        self.connect()
                        time.sleep(1)
                        continue

                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (self.height, self.width, 3)
                    ).copy()

                # =========================
                # BUFFER
                # =========================
                with self.lock:
                    self.buffer.append(frame)
                    self.last_frame_time = time.time()

                if self.is_local_file or self.is_webcam:
                    time.sleep(self.frame_interval)

            except Exception as e:
                print("[CAMERA] Erro:", e)
                self.connect()
                time.sleep(self.reconnect_delay)

    # =========================
    # LEITURA EXTERNA
    # =========================
    def read(self):
        with self.lock:
            if self.buffer:
                return True, self.buffer.popleft()
            return False, None

    # =========================
    # WATCHDOG INTELIGENTE
    # =========================
    def watchdog(self, timeout=10):
        if self.is_rtsp:
            if self.proc and self.proc.poll() is not None:
                print("[WATCHDOG] FFmpeg morreu, reiniciando...")
                self.connect()
                return

        if self.is_webcam:
            if time.time() - self.last_frame_time > timeout:
                print("[WATCHDOG] Webcam travou, reiniciando...")
                self.connect()
# =========================
# FUNÇÃO GET CAMERA (SINGLETON)
# =========================
def get_camera():
    global _camera_instance
    if _camera_instance is None:
        print(CAMERA_SOURCE_ENV)
        print(CAMERA_SOURCE_ENV)
        if CAMERA_SOURCE_ENV.isdigit():
            source = int(CAMERA_SOURCE_ENV)
        else:
            source = CAMERA_SOURCE_ENV
        _camera_instance = CameraSource(source, width=640, height=360)
    return _camera_instance

# =========================
# LOOP DE STREAM
# =========================
def gen_frames(camera):
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
            # 🔵 VEÍCULO (azul)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            if (x2 - x1) * (y2 - y1) < MIN_VEHICLE_AREA:
                continue
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

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
                    if pid and ACTIVE_PLATES[pid]["authorized"]:
                        continue
                else:
                    pid = str(uuid.uuid4())
                    ACTIVE_PLATES[pid] = {
                        "bbox": (ax1, ay1, ax2, ay2),
                        "last_seen": now,
                        "last_event": 0,
                        "status": "new",
                        "reads": [],
                        "authorized": False,
                        "ocr_skip": 0
                    }

                # =========================
                # OCR PIPELINE
                # =========================
                crop_plate = frame[ay1:ay2, ax1:ax2]

                if crop_plate.size == 0:
                    continue

                # Pré-processamento
                gray = cv2.cvtColor(crop_plate, cv2.COLOR_BGR2GRAY)
                processed = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)[1]
                processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

                plate_text = None

                if OCR_ENABLED:
                    ACTIVE_PLATES[pid]["ocr_skip"] += 1

                    if ACTIVE_PLATES[pid]["ocr_skip"] >= OCR_FRAME_SKIP:
                        ACTIVE_PLATES[pid]["ocr_skip"] = 0
                        plate_text = read_plate_ocr(processed)

                # =========================
                # PROCESSAMENTO OCR
                # =========================
                if plate_text:
                    ACTIVE_PLATES[pid]["reads"].append(plate_text)

                    if len(ACTIVE_PLATES[pid]["reads"]) > 10:
                        ACTIVE_PLATES[pid]["reads"].pop(0)

                    if len(ACTIVE_PLATES[pid]["reads"]) >= CONFIRMATION_THRESHOLD:
                        final_plate = most_common(ACTIVE_PLATES[pid]["reads"])

                                                
                        whitelist = load_whitelist_cached()
                        token = plate_token(final_plate)

                        if token in whitelist and not ACTIVE_PLATES[pid]["authorized"]:
                            print(f"[ACCESS] AUTORIZADO: {final_plate}")

                            trigger_gate()

                            # ✅ AGORA SIM salva evento
                            save_event(frame, (ax1, ay1, ax2, ay2), pid)

                            ACTIVE_PLATES[pid]["authorized"] = True
                            ACTIVE_PLATES[pid]["last_event"] = now
                            ACTIVE_PLATES[pid]["status"] = "sent"

                # =========================
                # DEBUG VISUAL
                # =========================
                if plate_text:
                    cv2.putText(frame, plate_text, (ax1, ay1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

                if SHOW_BORDER_IDENTIFICATION:
                    if ACTIVE_PLATES[pid]["authorized"]:
                        color = (0, 255, 0)  # 🟢 autorizado
                    else:
                        color = (0, 0, 255)  # 🔴 não autorizado

                    cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), color, 2)

        cv2.putText(frame, f"FPS: {fps}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        ret, buf = cv2.imencode(".jpg", frame)
        yield b"--frame\r\nContent-Type:image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

# =========================
# ROTAS FLASK
# =========================
@stream_bp.route("/video_feed")
def video_feed():
    camera = get_camera()

    return Response(gen_frames(camera), mimetype="multipart/x-mixed-replace; boundary=frame")

@stream_bp.route("/health")
def health():
    camera = get_camera()
    now = time.time()
    camera_ok = (camera.cap is not None and camera.cap.isOpened()) or camera.proc is not None
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
