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

URL_API = "https://3000-firebase-prjfaceplate-1756233490639.cluster-mdgxqvvkkbfpqrfigfiuugu5pk.cloudworkstations.dev"
LOGIN_ENDPOINT = f"{URL_API}/api/auth"

# Credenciais de login
LOGIN_PAYLOAD = {
    "email": "sjf.vinicius@gmail.com",
    "pwd": "Vinicius@20012"
}

auth_token = None



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
last_status_txt = None
last_api_status = None
last_status_color = (0, 0, 255)
last_status_time = 0
DISPLAY_DURATION = 3  # segundos que vai ficar na tela

def authenticate():
    global auth_token
    try:
        
        resp = requests.post(LOGIN_ENDPOINT, json=LOGIN_PAYLOAD, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        
        token = data.get('user', {}).get("token")

        if not token:
            raise RuntimeError("Token não retornado pelo endpoint de login.")

        auth_token = token
        print("✅ Login bem-sucedido. Token obtido.")

    except Exception as e:
        print(f"❌ Erro ao autenticar: {e}")
        raise

def gen_frames(CAMERA_SOURCE):
    global last_plate_detected, consecutive_count
    global last_status_txt, last_status_color, last_status_time, last_api_status

    cap = cv2.VideoCapture(CAMERA_SOURCE)
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir a fonte de vídeo: {CAMERA_SOURCE}")

    skip_counter = 0
    fail_count = 0
    MAX_FAILS = 20
    while True:
        success, frame = cap.read()

        # if not success:
        #     fail_count += 1
        #     print(f"⚠️ Falha ao ler frame ({fail_count}/{MAX_FAILS})")

        #     if fail_count >= MAX_FAILS:
        #         print("🔄 Tentando reabrir conexão com a câmera...")
        #         cap.release()
        #         time.sleep(2)  # dá um tempinho antes de tentar de novo
        #         cap = cv2.VideoCapture(CAMERA_SOURCE)
        #         fail_count = 0
        #         if not cap.isOpened():
        #             print("❌ Não foi possível reconectar à câmera.")
        #             time.sleep(5)  # espera mais antes da próxima tentativa
        #             continue
        #         else:
        #             print("✅ Reconexão bem-sucedida.")

        #     continue  # tenta ler o próximo frame
        # else:
        #     fail_count = 0  # reset se conseguir ler

        if frame is None:
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
    
                cv2.rectangle(frame, (x1, y1), (x2, y2), (237, 146, 66), 2)

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
                    cv2.putText(frame, plate_text, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (237, 146, 66), 2)

                    if plate_text == last_plate_detected:
                        consecutive_count += 1
                    else:
                        last_plate_detected = plate_text
                        consecutive_count = 1


                    if consecutive_count >= CONSECUTIVE_THRESHOLD:
                        try:
                            plate_text = plate_text[:3].replace("0", "O") + plate_text[3:]
                            
                            payload = {"plate": plate_text}
                            headers = {
                                "Cookie": f"nextauthprjfaceplate-token={auth_token}"
                            }
                            response = requests.post(f"{URL_API}/api/isvalidvehicle", json=payload, headers=headers, timeout=10)
                            
                            if response.status_code == 200:
                                data = response.json()
                                last_api_status = f"Placa {plate_text}: HABILITADA"
                                last_status_color = (237, 146, 66)
                            else:
                                last_api_status = f"Placa {plate_text}: INVALIDA"
                                last_status_color = (66, 66, 237)

                        except Exception as e:
                            last_api_status = f"Erro API: {e}"
                            last_status_color = (66, 66, 237)

                        last_status_time = time.time()  # marca o momento para exibir o texto
                        consecutive_count = 0

        # desenha o último status se ainda não expirou
        if last_api_status and (time.time() - last_status_time) < DISPLAY_DURATION:
            h, w, _ = frame.shape
            text = last_api_status
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1
            thickness = 2
            (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

            pad_x, pad_y = 20, 10
            rect_w = text_w + 2 * pad_x
            rect_h = text_h + 2 * pad_y
            rect_x1 = w//2 - rect_w//2
            rect_y1 = h//2 - rect_h//2
            rect_x2 = rect_x1 + rect_w
            rect_y2 = rect_y1 + rect_h

            # bg_color = (237, 146, 66)  # BGR
            cv2.rectangle(frame, (rect_x1, rect_y1), (rect_x2, rect_y2), last_status_color, -1)
            text_x = rect_x1 + pad_x
            text_y = rect_y1 + pad_y + text_h
            cv2.putText(frame, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
        else:
            last_api_status = None

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@stream_bp.route('/video_feed')
def video_feed():
    return Response(gen_frames(CAMERA_SOURCE),
        mimetype='multipart/x-mixed-replace; boundary=frame')
