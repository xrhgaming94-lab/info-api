#MADE BY @STAR_GMR
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
from flask import Flask, jsonify, request
from data_pb2 import AccountPersonalShowInfo
from google.protobuf.json_format import MessageToDict
import uid_generator_pb2
import threading
import time

app = Flask(__name__)

jwt_token = None
jwt_lock = threading.Lock()
region_cache = {}

# ---------------- JWT CONFIG ----------------
JWT_API = "https://star-jwt-gen.vercel.app/token"

JWT_CREDENTIALS = {
    "IND": {"uid": "4569404695", "password": "RAGHAVLIKESBOT_RAGHAV_2THCG"},
    "BD":  {"uid": "4331389599", "password": "Sumon523022_BREXX_4KQT9"},
    "ME":  {"uid": "4275417742", "password": "CCBD38AAC5A1FA5807FD683B6DD0EE6C5F4F7447DD51C6D30062CD425B10E493"},
    "PK":  {"uid": "4680926895", "password": "gamer-07G3N3MND-X64"},
    "TH":  {"uid": "4331389599", "password": "Sumon523022_BREXX_4KQT9"},
    "BR":  {"uid": "4514032809", "password": "F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E"},
    "VN":  {"uid": "4331389599", "password": "Sumon523022_BREXX_4KQT9"},
    "SAC":  {"uid": "4514032809", "password": "F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E"},
    "ID":  {"uid": "4708244360", "password": "IDOY-QSKOPFJYU-SG"},
}

# ---------------- REGION DETECTION ----------------
def detect_region(uid):
    """Detect region automatically using topup.pk API"""
    try:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-MM,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://topup.pk",
            "Referer": "https://topup.pk/",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Android WebView";v="138"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; RMX5070 Build/UKQ1.231108.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.157 Mobile Safari/537.36",
            "X-Requested-With": "mark.via.gp",
            "Cookie": "source=mb; region=PK; mspid2=13c49fb51ece78886ebf7108a4907756; _fbp=fb.1.1753985808817.794945392376454660; language=en; datadome=WQaG3HalUB3PsGoSXY3TdcrSQextsSFwkOp1cqZtJ7Ax4YkiERHUgkgHlEAIccQO~w8dzTGM70D9SzaH7vymmEqOrVeX5pIsPVE22Uf3TDu6W3WG7j36ulnTg2DltRO7; session_key=hq02g63z3zjcumm76mafcooitj7nc79y",
        }
        
        payload = {
            "app_id": 100067,
            "login_id": str(uid)
        }
        
        response = requests.post("https://topup.pk/api/auth/player_id_login", headers=headers, json=payload, timeout=10)
        data = response.json() if response.text else {}
        
        region = data.get('region', '').upper()
        
        # Map regions to supported format
        region_map = {
            'IN': 'IND', 'INDIA': 'IND',
            'BD': 'BD', 'BANGLADESH': 'BD',
            'PK': 'PK', 'PAKISTAN': 'PK',
            'ME': 'ME',
            'BR': 'BR', 'BRAZIL': 'BR',
            'TH': 'TH', 'THAILAND': 'TH',
            'VN': 'VN', 'VIETNAM': 'VN',
            'ID': 'ID', 'INDONESIA': 'ID'
        }
        
        detected = region_map.get(region, 'IND')
        
        if detected in JWT_CREDENTIALS:
            return detected
        return 'IND'
        
    except Exception as e:
        print(f"[REGION DETECTION ERROR] {e}")
        return 'IND'

# ---------------- JWT HANDLING ----------------
def get_jwt_token_sync(region):
    global jwt_token

    creds = JWT_CREDENTIALS.get(region, JWT_CREDENTIALS["IND"])
    url = f"{JWT_API}?uid={creds['uid']}&password={creds['password']}"

    with jwt_lock:
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if isinstance(data, dict) and "token" in data:
                jwt_token = data["token"]
                return jwt_token
        except Exception as e:
            print("[JWT ERROR]", e)

    return None

def ensure_jwt_token_sync(region):
    global jwt_token
    if not jwt_token:
        return get_jwt_token_sync(region)
    return jwt_token

def jwt_token_updater(region):
    while True:
        get_jwt_token_sync(region)
        time.sleep(300)

# ---------------- API ENDPOINT ----------------
def get_api_endpoint(region):
    endpoints = {
        "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "BD":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "ME":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "PK":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "TH":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "BR":  "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "VN":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "SAC":  "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "ID":  "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    }
    return endpoints.get(region, endpoints["IND"])

# ---------------- AES ----------------
AES_KEY = "Yg&tc%DEuh6%Zc^8"
AES_IV  = "6oyZDr22E3ychjM%"

def encrypt_aes(hex_data):
    cipher = AES.new(AES_KEY.encode()[:16], AES.MODE_CBC, AES_IV.encode()[:16])
    padded = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return binascii.hexlify(encrypted).decode()

# ---------------- MAIN API CALL ----------------
def call_api(enc_hex, region):
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception("JWT token not available")

    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; Android 9)",
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB53",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    r = requests.post(
        get_api_endpoint(region),
        headers=headers,
        data=bytes.fromhex(enc_hex),
        timeout=10
    )

    return r.content.hex()

# ---------------- ROUTES ----------------
@app.route("/accinfo")
def info():
    try:
        uid = request.args.get("uid")
        region = request.args.get("region")  # Optional now
        
        if not uid:
            return jsonify({"error": "UID required"}), 400
        
        # Auto-detect region if not provided
        auto_detected = False
        if not region:
            region = detect_region(uid)
            auto_detected = True
            print(f"[AUTO DETECT] UID {uid} -> Region {region}")
        
        region = region.upper()
        
        # Validate region
        valid_regions = ["IND", "BD", "PK", "ME", "BR", "TH", "VN", "SAC", "ID"]
        if region not in valid_regions:
            return jsonify({"error": f"Invalid region: {region}. Valid regions: {', '.join(valid_regions)}"}), 400

        # Start JWT updater thread (only once per region)
        if region not in region_cache:
            region_cache[region] = True
            threading.Thread(target=jwt_token_updater, args=(region,), daemon=True).start()

        msg = uid_generator_pb2.uid_generator()
        msg.saturn_ = int(uid)
        msg.garena = 1

        hex_data = binascii.hexlify(msg.SerializeToString()).decode()
        encrypted = encrypt_aes(hex_data)

        api_hex = call_api(encrypted, region)

        pb = AccountPersonalShowInfo()
        pb.ParseFromString(bytes.fromhex(api_hex))
        data = MessageToDict(pb)

        data["Developer"] = "@STAR_GMR"
        data["Channel"] = "@STAR_METHODE"
        data["Region"] = region
        data["Auto_Detected"] = auto_detected
        data["Version"] = "OB53"

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return jsonify({
        "message": "Free Fire Account Info API with Auto Region Detection",
        "developer": "@STAR_GMR",
        "channel": "@STAR_METHODE",
        "endpoint": "/accinfo?uid=UID&region=IND (region optional)",
        "example": {
            "with_region": "http://localhost:8080/accinfo?uid=1868812498&region=IND",
            "auto_region": "http://localhost:8080/accinfo?uid=1868812498"
        }
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║   Free Fire API with Auto Region         ║
    ║   Developer: @STAR_GMR                   ║
    ║   Channel: @STAR_METHODE                 ║
    ╚══════════════════════════════════════════╝
    """)
    ensure_jwt_token_sync("IND")
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)