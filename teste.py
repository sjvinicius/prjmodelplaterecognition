from onvif import ONVIFCamera
import cv2

IP = "192.168.15.14"
PORT = 5000
USER = "sjf.vinicius@gmail.com"
PASSWORD = "Vinicius@20012"

cam = ONVIFCamera(IP, PORT, USER, PASSWORD)
media = cam.create_media_service()
profiles = media.GetProfiles()

# Lista de streams
streams = []

for p in profiles:
    token = p.token
    uri = media.GetStreamUri({
        "StreamSetup": {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"}
        },
        "ProfileToken": token
    })
    print("\nPROFILE:", p.Name)
    print("RTSP:", uri.Uri)
    streams.append((p.Name, uri.Uri))

# Abrir cada stream com OpenCV
caps = [cv2.VideoCapture(url) for _, url in streams]

while True:
    for i, cap in enumerate(caps):
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cv2.imshow(streams[i][0], frame)  # Nome da janela = perfil
    if cv2.waitKey(1) & 0xFF == 27:  # ESC para sair
        break

for cap in caps:
    cap.release()
cv2.destroyAllWindows()
