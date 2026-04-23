import base64
import binascii
import threading
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from flask import Flask, request, jsonify
from google.protobuf.json_format import MessageToDict

import uid_generator_pb2
from data_pb2 import AccountPersonalShowInfo

app = Flask(__name__)
jwt_token = None
jwt_lock = threading.Lock()

# ---------------- REGION FINDER (from region.py) ----------------
def find_region_by_uid(uid):
    """Fetch region using UID from topup.pk API"""
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

    payload = {"app_id": 100067, "login_id": str(uid)}

    try:
        response = requests.post(
            "https://topup.pk/api/auth/player_id_login",
            headers=headers,
            json=payload,
            timeout=15,
        )
        data = response.json() if response.text else {}
        region = data.get("region", "")
        return region.upper() if region else None
    except Exception as e:
        print(f"[REGION FINDER] Error: {e}")
        return None


# ---------------- JWT HANDLING ----------------
def extract_token_from_response(data, region):
    if not isinstance(data, dict):
        return None

    if "token" in data and data.get("status") in ["live", "success"]:
        return data["token"]

    if data.get("success") is True and "token" in data:
        return data["token"]

    if region == "IND":
        if data.get("status") in ["success", "live"]:
            return data.get("token")
    elif region in ["BR", "US", "SAC", "BD", "PK", "VN", "ME", "TH", "ID"]:
        return data.get("token")

    return data.get("token")


def get_jwt_token_sync(region):
    """Fetch JWT token synchronously for a region."""
    global jwt_token
    endpoints = {
        "IND": "http://star-jwt-gen.vercel.app/token?uid=4569404695&password=RAGHAVLIKESBOT_RAGHAV_2THCG",
        "BR": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
        "US": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
        "SAC": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
        "BD": "https://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
        "ID": "http://star-jwt-gen.vercel.app/token?uid=4708244360&password=IDOY-QSKOPFJYU-SG",
        "PK": "http://star-jwt-gen.vercel.app/token?uid=4680926895&password=gamer-07G3N3MND-X64",
        "VN": "http://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
        "ME": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=CCBD38AAC5A1FA5807FD683B6DD0EE6C5F4F7447DD51C6D30062CD425B10E493",
        "TH": "http://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
        "default": "http://star-jwt-gen.vercel.app/token?uid=4658804976&password=VISIT_API_BY_KAISER_KBKP4_BY_STAR_GMR_QIMU2",
    }
    url = endpoints.get(region, endpoints["default"])

    with jwt_lock:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            token = extract_token_from_response(data, region)
            if token:
                jwt_token = token
                print(f"[JWT] Token for {region} updated: {token[:50]}...")
                # Small delay to ensure token is valid
                time.sleep(0.5)
                return jwt_token
            else:
                print(f"[JWT] Failed to extract token from response for {region}")
        except Exception as e:
            print(f"[JWT] Request error for {region}: {e}")
    return None


def ensure_jwt_token_sync(region):
    """Ensure JWT token is available; fetch if missing."""
    global jwt_token
    if not jwt_token:
        print(f"[JWT] Token missing for {region}. Fetching...")
        return get_jwt_token_sync(region)
    return jwt_token


def jwt_token_updater(region):
    """Background thread to refresh JWT every 5 minutes."""
    while True:
        get_jwt_token_sync(region)
        time.sleep(300)


# ---------------- API ENDPOINTS ----------------
def get_api_endpoint(region):
    endpoints = {
        "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "US": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "SAC": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "BD": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "ID": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "PK": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "VN": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "ME": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "TH": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "default": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
    }
    return endpoints.get(region, endpoints["default"])


# ---------------- AES ENCRYPTION ----------------
default_key = "Yg&tc%DEuh6%Zc^8"
default_iv = "6oyZDr22E3ychjM%"


def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()


# ---------------- API CALL WITH RETRY ----------------
def apis(idd, region, retry_count=0):
    """API call with automatic retry on 401 error"""
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception(f"Failed to get JWT token for region {region}")

    endpoint = get_api_endpoint(region)
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        "Connection": "Keep-Alive",
        "Expect": "100-continue",
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB53",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        data = bytes.fromhex(idd)
        response = requests.post(endpoint, headers=headers, data=data, timeout=10)
        
        # If unauthorized and we haven't retried too many times
        if response.status_code == 401 and retry_count < 2:
            print(f"[API] Got 401, refreshing token and retrying... (attempt {retry_count + 1})")
            # Force refresh token
            global jwt_token
            with jwt_lock:
                jwt_token = None
            # Wait a bit before retry
            time.sleep(1)
            # Retry with fresh token
            return apis(idd, region, retry_count + 1)
        
        response.raise_for_status()
        return response.content.hex()
        
    except requests.exceptions.RequestException as e:
        print(f"[API] Request to {endpoint} failed: {e}")
        raise


# ---------------- FLASK ROUTES ----------------
@app.route("/accinfo", methods=["GET"])
def get_player_info():
    try:
        uid = request.args.get("uid")
        region = request.args.get("region", "").upper()
        custom_key = request.args.get("key", default_key)
        custom_iv = request.args.get("iv", default_iv)

        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400

        # ----- AUTO REGION DETECTION -----
        detected_region = None
        if not region:
            print(f"[INFO] No region provided, auto-detecting for UID: {uid}")
            detected_region = find_region_by_uid(uid)
            if detected_region:
                region = detected_region
                print(f"[INFO] Auto-detected region: {region}")
            else:
                return jsonify(
                    {
                        "error": "Could not auto-detect region. Please provide region parameter manually (IND, US, BR, PK, etc.)"
                    }
                ), 400
        else:
            print(f"[INFO] Using provided region: {region}")

        # Start background JWT updater (only once per region)
        if not hasattr(app, 'jwt_threads'):
            app.jwt_threads = {}
        if region not in app.jwt_threads:
            thread = threading.Thread(target=jwt_token_updater, args=(region,), daemon=True)
            thread.start()
            app.jwt_threads[region] = thread
            print(f"[INFO] Started JWT updater thread for region: {region}")

        # Generate protobuf
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        protobuf_data = message.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()

        # Encrypt
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)

        # Call API with retry logic
        api_response = apis(encrypted_hex, region)
        if not api_response:
            return jsonify({"error": "Empty response from API"}), 400

        # Parse response
        message = AccountPersonalShowInfo()
        message.ParseFromString(bytes.fromhex(api_response))
        result = MessageToDict(message)
        result["Owners"] = ["𝗦𝗧𝗔𝗥 𝗚𝗔𝗠𝗘𝗥!!"]
        result["detected_region"] = detected_region or region
        return jsonify(result)

    except ValueError:
        return jsonify({"error": "Invalid UID format"}), 400
    except Exception as e:
        print(f"[ERROR] Processing request: {e}")
        return jsonify({"error": f"Failure to process the data: {str(e)}"}), 500


@app.route("/favicon.ico")
def favicon():
    return "", 404


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🔥 Server Started! 🔥")
    print("📍 Usage:")
    print("   With auto region:  /accinfo?uid=1868812498")
    print("   With manual region: /accinfo?uid=1868812498&region=IND")
    print("   With custom key/iv: /accinfo?uid=1868812498&region=IND&key=yourkey&iv=youriv")
    app.run(host="0.0.0.0", port=5552)