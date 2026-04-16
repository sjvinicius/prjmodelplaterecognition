import requests
import os
import json
import time
from flask import Blueprint, request, jsonify
from Crypto.Cipher import AES
import base64

whitelist_bp = Blueprint("whitelist", __name__)

WHITELIST_FILE = os.getenv("WHITELIST_FILE", "whitelist.json")

EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")

_whitelist_cache = set()
_last_load = 0

def fetch_external_plates():

    print("[API] FETCH EXTERNAL PLATES");
    response = requests.get(
        EXTERNAL_API_URL,
        headers={
            "x-api-key": f"{os.getenv('ORANGE_PI_SECRET')}"
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


_whitelist_cache = set()

def sync_whitelist():
    global _whitelist_cache, _last_load

    encrypted_plates = fetch_external_plates()

    tokens = set()

    for encrypted in encrypted_plates:
        print("[RAW API]", encrypted)

        # plate = decrypt_token(encrypted)
        plate = encrypted

        if not plate:
            continue

        normalized = plate_token(plate)

        if normalized:
            tokens.add(normalized)

    save_whitelist(tokens)

    _whitelist_cache = tokens
    _last_load = time.time()

    print(f"[SYNC] OK - {len(tokens)} placas")

    return tokens

_last_load = 0

def load_whitelist():
    if not os.path.exists(WHITELIST_FILE):
        return set()

    try:
        with open(WHITELIST_FILE, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return set()

        return set(data)

    except Exception as e:
        print("[WHITELIST LOAD ERROR]", e)
        return set()


def load_whitelist_cached(ttl=5):
    global _whitelist_cache, _last_load

    now = time.time()

    if now - _last_load > ttl:
        _whitelist_cache = load_whitelist()
        _last_load = now

    return _whitelist_cache

def decrypt_token(token):
    try:
        if ":" not in token:
            print("[DECRYPT SKIP] formato inválido:", token)
            return None
        
        iv_hex, encrypted_hex = token.split(":")

        iv = bytes.fromhex(iv_hex)
        encrypted = bytes.fromhex(encrypted_hex)

        key = base64.urlsafe_b64decode(os.getenv('ORANGE_PI_SECRET'))

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)

        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]

        return decrypted.decode("utf-8")

    except Exception as e:
        print("[DECRYPT ERROR]", token, e)
        return None

def load_whitelist_decrypted():
    encrypted_list = load_whitelist_cached()
    result = set()

    for t in encrypted_list:
        plate = decrypt_token(t)
        if plate:
            result.add(plate_token(plate))

    return result

def plate_token(plate: str):
    if not plate:
        return None

    return plate.replace("-", "").replace(" ", "").upper()