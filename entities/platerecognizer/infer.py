from flask import Blueprint, request, jsonify
import io
import easyocr
from PIL import Image
from ultralytics import YOLO

reader = easyocr.Reader(["en"])
infer_bp = Blueprint('infer_bp', __name__)
yolo = YOLO("models/LP-detection.pt") 

@infer_bp.route('/infer', methods=['POST'])
def infer():
    if "image" not in request.files:
        return jsonify({"error": "Envie um arquivo de imagem em 'image'"}), 400

    file = request.files["image"]
    img = Image.open(file.stream).convert("RGB")

    results = yolo.predict(img, conf=0.25, imgsz=640)
    plates = []

    for r in results:
        for box in r.boxes:
            det_conf = float(box.conf.cpu().item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())

            plate_crop = img.crop((x1, y1, x2, y2))

            buf = io.BytesIO()
            plate_crop.save(buf, format="JPEG")
            ocr_results = reader.readtext(buf.getvalue())

            for (_, text, ocr_conf) in ocr_results:
                clean = "".join(ch for ch in text if ch.isalnum()).upper()
                if 6 < len(clean) < 8: 
                    plates.append({
                        "plate": clean,
                        "conf": float(ocr_conf),
                        "bbox": [x1, y1, x2 - x1, y2 - y1],
                        "det_conf": det_conf
                    })

    return jsonify({"plates": plates})
