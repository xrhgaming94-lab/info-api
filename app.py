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
    
    #https://kallu-jwt-token.vercel.app/

def get_jwt_token_sync(region):
    """Fetch JWT token synchronously for a region."""
    global jwt_token
    endpoints = {
    "IND": "http://star-jwt-gen.vercel.app/token?uid=4569404695&password=RAGHAVLIKESBOT_RAGHAV_2THCG",
    "BR": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "US": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "SAC": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "BD": "https://star-jwt-gen.vercel.app/token?uid=4664973977&password=S_Y0QTY_BY_STAR_GMR_NRETK",
    "ID": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "PK": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "VN": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "ME": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "TH": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=DANGER-LPN34CEIS-CORE",
    "default": "http://star-jwt-gen.vercel.app/token?uid=4658804976&password=VISIT_API_BY_KAISER_KBKP4_BY_STAR_GMR_QIMU2"
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
        "default": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
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

# ---------------- API CALL ----------------
def apis(idd, region):
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception(f"Failed to get JWT token for region {region}")
    
    endpoint = get_api_endpoint(region)
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB53',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    try:
        data = bytes.fromhex(idd)
        response = requests.post(endpoint, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        return response.content.hex()
    except requests.exceptions.RequestException as e:
        print(f"[API] Request to {endpoint} failed: {e}")
        raise

# ---------------- FLASK ROUTES ----------------
@app.route('/accinfo', methods=['GET'])
def get_player_info():
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'default').upper()
        custom_key = request.args.get('key', default_key)
        custom_iv = request.args.get('iv', default_iv)
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400
        
        # Start background JWT updater
        threading.Thread(target=jwt_token_updater, args=(region,), daemon=True).start()
        
        # Generate protobuf
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        protobuf_data = message.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()
        
        # Encrypt
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)
        
        # Call API
        api_response = apis(encrypted_hex, region)
        if not api_response:
            return jsonify({"error": "Empty response from API"}), 400
        
        # Parse response
        message = AccountPersonalShowInfo()
        message.ParseFromString(bytes.fromhex(api_response))
        result = MessageToDict(message)
        result['Owners'] = ['𝗦𝗧𝗔𝗥 𝗚𝗔𝗠𝗘𝗥¡¡!!']
        return jsonify(result)
    
    except ValueError:
        return jsonify({"error": "Invalid UID format"}), 400
    except Exception as e:
        print(f"[ERROR] Processing request: {e}")
        return jsonify({"error": f"Failure to process the data: {str(e)}"}), 500

@app.route('/favicon.ico')
def favicon():
    return '', 404

# ---------------- MAIN ----------------
if __name__ == "__main__":
    ensure_jwt_token_sync("default")
    app.run(host="0.0.0.0", port=5552)
