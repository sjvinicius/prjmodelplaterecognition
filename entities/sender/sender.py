import os
import json
import time
import requests

EVENTS_DIR = "events"
API_ENDPOINT = os.getenv("API_ENDPOINT")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN")
RETRY_INTERVAL = int(os.getenv("RETRY_INTERVAL", 10))

HEADERS = {
    "Authorization": f"Bearer {DEVICE_TOKEN}"
}

def send_event(json_path):
    with open(json_path, "r") as f:
        metadata = json.load(f)

    image_path = metadata["image"]

    if not os.path.exists(image_path):
        print(f"❌ Imagem não encontrada: {image_path}")
        os.remove(json_path)
        return

    files = {
        "image": open(image_path, "rb")
    }

    data = {
        "device_id": metadata.get("event_id"),
        "timestamp": metadata.get("timestamp"),
        "bbox": json.dumps(metadata.get("bbox")),
    }

    resp = requests.post(
        API_ENDPOINT,
        headers=HEADERS,
        data=data,
        files=files,
        timeout=15
    )

    if resp.status_code == 200:
        print(f"✅ Evento enviado: {json_path}")
        os.remove(json_path)
        os.remove(image_path)
    else:
        raise RuntimeError(f"Erro {resp.status_code}: {resp.text}")

def main():
    print("📡 Sender iniciado")

    while True:
        try:
            files = sorted(
                f for f in os.listdir(EVENTS_DIR) if f.endswith(".json")
            )

            for file in files:
                json_path = os.path.join(EVENTS_DIR, file)
                try:
                    send_event(json_path)
                except Exception as e:
                    print(f"⚠️ Falha ao enviar {file}: {e}")
                    break  # evita loop infinito rápido

        except Exception as e:
            print(f"❌ Erro geral no sender: {e}")

        time.sleep(RETRY_INTERVAL)

if __name__ == "__main__":
    main()
