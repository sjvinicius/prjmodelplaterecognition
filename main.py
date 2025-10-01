import os
import time
import traceback
from flask import Flask
from entities.platerecognizer.infer import infer_bp
from entities.streaming.streaming import stream_bp, authenticate

app = Flask(__name__)
app.register_blueprint(infer_bp)
app.register_blueprint(stream_bp)

# @app.before_first_request
# def init_auth():
#     authenticate()

@app.route('/')
def index():
    authenticate()
    return '''
        <h1>Monitoramento de Placas 🚗</h1>
        <img src="/video_feed" width="800">
    '''

if __name__ == "__main__":
    while True:
        try:
            app.run(debug=True, use_reloader=False, host="0.0.0.0", port=3000)
        except Exception:
            traceback.print_exc()
            print("Aplicação travou! Reiniciando em 5 segundos...")
            time.sleep(5)
