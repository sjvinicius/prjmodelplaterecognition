import io
import requests
from flask import Blueprint, Response
from PIL import Image
import cv2
import easyocr
from ultralytics import YOLO
import os
import time

stream_bp = Blueprint('stream_bp', __name__)

# Configurações
MIN_PLATE_AREA = 30000  # Tamanho da area de captura
CONSECUTIVE_THRESHOLD = 3  # Leituras consecutivas necessárias
INFER_URL = "https://5000-firebase-prjplaterecog-1755611185279.cluster-j6d3cbsvdbe5uxnhqrfzzeyj7i.cloudworkstations.dev/infer"  # endpoint da API infer

reader = easyocr.Reader(["en"])
yolo = YOLO("models/LP-detection.pt")

# Variáveis para rastrear leituras consecutivas
last_plate = None
consecutive_count = 0
# Fonte de vídeo: pode ser índice da câmera, URL RTSP, arquivo .mp4, etc. 
# Exemplo: 
# CAMERA_SOURCE = 0 
# Webcam local 
# CAMERA_SOURCE = "rtsp://user:pass@ip" 
# Câmera IP RTSP 
# CAMERA_SOURCE = "http://ip/video" # Stream HTTP # CAMERA_SOURCE = "video.mp4" # Arquivo de vídeo
CAMERA_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "resources/video480p.mp4"
)
FRAME_SKIP = 20
last_plate_detected = None
last_plate_sent = None
last_status_txt = None
last_status_color = (0, 0, 255)
last_status_time = 0
DISPLAY_DURATION = 3  # segundos que vai ficar na tela

def gen_frames(CAMERA_SOURCE):
    global last_plate_detected, last_plate_sent, consecutive_count
    global last_status_txt, last_status_color, last_status_time

    cap = cv2.VideoCapture(CAMERA_SOURCE)
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte de vídeo: {CAMERA_SOURCE}")

    skip_counter = 0

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue 
        

        if skip_counter < FRAME_SKIP:
            skip_counter += 1
            continue
        skip_counter = 0

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)

        results = yolo.predict(pil_img, conf=0.25, imgsz=640)
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                bbox_area = (x2 - x1) * (y2 - y1)
                # if bbox_area < MIN_PLATE_AREA:
                #     continue
    
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

                plate_crop = pil_img.crop((x1, y1, x2, y2))
                buf = io.BytesIO()
                plate_crop.save(buf, format="JPEG")
                ocr_results = reader.readtext(buf.getvalue())

                plate_text = ""
                for (_, text, _) in ocr_results:
                    clean = "".join(ch for ch in text if ch.isalnum()).upper()
                    if 6 <= len(clean) <= 8:
                        plate_text = clean

                if plate_text:
                    if plate_text == last_plate_detected:
                        consecutive_count += 1
                    else:
                        last_plate_detected = plate_text
                        consecutive_count = 1

                    if consecutive_count >= CONSECUTIVE_THRESHOLD and plate_text != last_plate_sent:
                        status_txt = f"Placa {plate_text}: HABILITADA"
                        color = (0, 255, 0)

                        last_status_txt = status_txt
                        last_status_color = color
                        last_status_time = time.time()  # marca o momento
                        
                        # last_plate_sent = plate_text
                        consecutive_count = 0

        # desenha o último status se ainda não expirou
        if last_status_txt and (time.time() - last_status_time) < DISPLAY_DURATION:
            cv2.putText(frame, last_status_txt, (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, last_status_color, 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@stream_bp.route('/video_feed')
def video_feed():
    return Response(gen_frames(CAMERA_SOURCE),
        mimetype='multipart/x-mixed-replace; boundary=frame')
