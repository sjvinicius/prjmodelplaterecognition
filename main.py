import os
import time
import traceback
from flask import Flask
from entities.platerecognizer.infer import infer_bp
from entities.streaming.streaming import stream_bp
from entities.security.whitelist import whitelist_bp
# , authenticate
import json

app = Flask(__name__)
app.register_blueprint(infer_bp)
app.register_blueprint(stream_bp)
app.register_blueprint(whitelist_bp)

# @app.before_first_request
# def init_auth():
#     authenticate()

@app.route('/')
def index():
    return f'''
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Monitoramento de Placas</title>
        <style>
            :root {{
                --background: #ffffff;
                --foreground: #171717;
                --primary: #4292ED;
                --secondary: #575757;
                --tertiary: #ED4242;
            }}

            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            }}

            body {{
                background-color: var(--background);
                color: var(--foreground);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                min-height: 100vh;
                padding: 40px 20px;
            }}

            h1 {{
                color: var(--primary);
                margin-bottom: 20px;
                text-align: center;
            }}

            .video-container {{
                border: 4px solid var(--primary);
                border-radius: 12px;
                overflow: hidden;
                max-width: 90%;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}

            img {{
                width: 100%;
                height: auto;
                display: block;
            }}

            footer {{
                margin-top: 40px;
                color: var(--secondary);
                font-size: 0.9rem;
                text-align: center;
            }}

            .status {{
                margin-bottom: 20px;
                color: var(--tertiary);
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <h1>Monitoramento de Placas 🚗</h1>
        <div class="video-container">
            <img src="/video_feed" alt="Stream de Câmera">
        </div>
        <footer>
            &copy; {time.strftime('%Y')} FacePlate LTDA. Todos os direitos reservados.
        </footer>
    </body>
    </html>
    '''


if __name__ == "__main__":
    while True:
        try:
            # app.run(debug=True, use_reloader=False, host="0.0.0.0", port=3000)
             app.run(debug=False, use_reloader=False, host="0.0.0.0", port=3000)
        except Exception:
            traceback.print_exc()
            print("Aplicação travou! Reiniciando em 5 segundos...")
            time.sleep(5)
