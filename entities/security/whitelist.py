import requests

EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")

def external_login():
    response = requests.post(
        os.getenv("EXTERNAL_LOGIN_URL"),
        json={
            "email": os.getenv("EXTERNAL_EMAIL"),
            "password": os.getenv("EXTERNAL_PASSWORD")
        },
        timeout=10
    )

    if response.status_code != 200:
        raise Exception("Falha no login externo")

    data = response.json()

    # ajuste conforme retorno da API
    token = data.get("token")

    if not token:
        raise Exception("Token não encontrado no login externo")

    return token

def fetch_external_plates(token):
    response = requests.get(
        os.getenv("EXTERNAL_API_URL"),
        headers={
            "Authorization": f"Bearer {token}"
        },
        timeout=10
    )

    if response.status_code != 200:
        raise Exception("Erro ao buscar placas")

    return response.json()

def save_whitelist(tokens):
    tmp_file = WHITELIST_FILE + ".tmp"

    with open(tmp_file, "w") as f:
        json.dump(list(tokens), f, indent=4)

    os.replace(tmp_file, WHITELIST_FILE)

@whitelist_bp.route("/sync-whitelist", methods=["POST"])
def sync_whitelist():
    try:
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token não enviado"}), 401

        token = auth_header.split(" ")[1]

        if not verify_token(token):
            return jsonify({"error": "Token inválido"}), 401

        if request.remote_addr not in ["127.0.0.1"]:
            return 403

        # =========================
        # LOGIN EXTERNO
        # =========================
        external_token = external_login()

        # =========================
        # BUSCA PLACAS
        # =========================
        plates = fetch_external_plates(external_token)

        tokens = set()

        for plate in plates:
            if not isinstance(plate, str):
                continue

            # token_plate = plate_token(plate)
            token_plate = plate
            tokens.add(token_plate)

        save_whitelist(tokens)

        return jsonify({
            "message": "Whitelist sincronizada",
            "total": len(tokens)
        }), 200

    except Exception as e:
        print("[SYNC ERROR]", str(e))
        return jsonify({
            "error": str(e)
        }), 500