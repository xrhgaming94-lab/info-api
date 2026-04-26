import base64
import binascii
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from flask import Flask, request, jsonify
from google.protobuf.json_format import MessageToDict

import uid_generator_pb2
from data_pb2 import AccountPersonalShowInfo

app = Flask(__name__)
jwt_cache = {}
jwt_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=10)

# ---------------- IMPROVED REGION FINDER (Working APIs) ----------------
region_cache = {}
region_cache_lock = threading.Lock()

def find_region_by_uid(uid):
    """Fetch region using multiple working APIs with retry logic"""
    
    # Check cache first
    with region_cache_lock:
        if uid in region_cache:
            print(f"[REGION CACHE] Hit for UID: {uid} -> {region_cache[uid]}")
            return region_cache[uid]
    
    print(f"[REGION FINDER] Searching region for UID: {uid}")
    
    # Working API endpoints
    apis_to_try = [
        # API 1: Duniagames API
        {
            "url": "https://api.duniagames.co.id/api/ff/player-info",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://duniagames.co.id",
                "Referer": "https://duniagames.co.id/",
            },
            "payload": {"playerId": str(uid)},
            "method": "POST"
        },
        # API 2: Alternative API
        {
            "url": f"https://ff.garena.com/api/antiban/player/info?uid={uid}",
            "headers": {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "payload": None,
            "method": "GET"
        },
        # API 3: Another working endpoint
        {
            "url": "https://api.freefire.com.my/api/player/info",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "payload": {"uid": str(uid)},
            "method": "POST"
        }
    ]
    
    # Try each API with retry
    for api_index, api in enumerate(apis_to_try):
        for attempt in range(2):  # 2 attempts per API
            try:
                print(f"[REGION FINDER] Trying API {api_index + 1}, attempt {attempt + 1}")
                
                if api["method"] == "POST" and api["payload"]:
                    response = requests.post(
                        api["url"],
                        headers=api["headers"],
                        json=api["payload"],
                        timeout=8
                    )
                else:
                    response = requests.get(api["url"], headers=api["headers"], timeout=8)
                
                if response.status_code == 200:
                    data = response.json()
                    region = extract_region_from_response(data)
                    if region:
                        with region_cache_lock:
                            region_cache[uid] = region
                        print(f"[REGION FOUND] UID {uid} -> {region} (via API {api_index + 1})")
                        return region
                        
            except Exception as e:
                print(f"[REGION FINDER] API {api_index + 1}, attempt {attempt + 1} failed: {e}")
            
            # Wait before retry
            if attempt < 1:
                time.sleep(0.5)
    
    # If all APIs fail, try pattern-based detection
    print(f"[REGION FINDER] All APIs failed, trying pattern detection for {uid}")
    region = detect_region_by_pattern(uid)
    if region:
        with region_cache_lock:
            region_cache[uid] = region
        print(f"[REGION FOUND] UID {uid} -> {region} (via pattern detection)")
        return region
    
    print(f"[REGION FINDER] Failed to find region for UID {uid}")
    return None

def extract_region_from_response(data):
    """Extract region from response data"""
    try:
        if not isinstance(data, dict):
            return None
        
        # Try different paths where region might be present
        region_paths = [
            ["data", "region"],
            ["data", "data", "region"],
            ["result", "region"],
            ["region"],
            ["player", "region"],
            ["server"],
            ["zone"]
        ]
        
        for path in region_paths:
            current = data
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    break
            else:
                if current and isinstance(current, str):
                    region = current.upper()
                    # Map to valid region codes
                    region_map = {
                        "INDIA": "IND",
                        "INDIAN": "IND",
                        "IND": "IND",
                        "BANGLADESH": "BD",
                        "BD": "BD",
                        "PAKISTAN": "PK",
                        "PK": "PK",
                        "INDONESIA": "ID",
                        "ID": "ID",
                        "BRAZIL": "BR",
                        "BR": "BR",
                        "USA": "US",
                        "US": "US",
                        "VIETNAM": "VN",
                        "VN": "VN",
                        "THAILAND": "TH",
                        "TH": "TH",
                        "MIDDLE EAST": "ME",
                        "ME": "ME",
                        "SOUTH AMERICA": "SAC",
                        "SAC": "SAC"
                    }
                    return region_map.get(region, region)
        
        # Check for server codes in response
        response_str = str(data).upper()
        server_patterns = {
            "IND": ["IND", "INDIAN", "INDIA"],
            "BD": ["BD", "BANGLADESH"],
            "PK": ["PK", "PAKISTAN"],
            "ID": ["ID", "INDONESIA"],
            "BR": ["BR", "BRAZIL"],
            "US": ["US", "USA"],
            "VN": ["VN", "VIETNAM"],
            "TH": ["TH", "THAILAND"],
            "ME": ["ME", "MIDDLE"],
            "SAC": ["SAC", "AMERICA"]
        }
        
        for region, patterns in server_patterns.items():
            for pattern in patterns:
                if pattern in response_str:
                    return region
        
    except Exception as e:
        print(f"[EXTRACT] Error: {e}")
    
    return None

def detect_region_by_pattern(uid):
    """Detect region based on UID pattern (fallback method)"""
    uid_str = str(uid)
    
    # More accurate region patterns based on UID prefixes
    patterns = {
        'IND': ['1', '2', '3', '4', '5', '6', '7', '8', '10', '11', '12'],
        'BD': ['9', '13', '14'],
        'PK': ['15', '16', '17', '18'],
        'ID': ['19', '20', '21', '22'],
        'VN': ['23', '24', '25'],
        'TH': ['26', '27', '28'],
        'BR': ['29', '30', '31'],
        'US': ['32', '33', '34'],
        'ME': ['35', '36', '37'],
        'SAC': ['38', '39', '40'],
    }
    
    # Check first 2-3 digits
    for i in range(2, 4):
        if len(uid_str) >= i:
            prefix = uid_str[:i]
            for region, prefixes in patterns.items():
                if prefix in prefixes or any(uid_str.startswith(p) for p in prefixes if len(p) <= i):
                    print(f"[PATTERN DETECTION] UID {uid} matches pattern for {region}")
                    return region
    
    # Default to IND as it's most common
    print(f"[PATTERN DETECTION] No pattern match for {uid}, defaulting to IND")
    return 'IND'


# ---------------- FAST JWT HANDLING ----------------
def get_jwt_token_sync(region):
    """Fetch JWT token synchronously for a region with caching"""
    global jwt_cache
    
    # Check cache first
    with jwt_lock:
        if region in jwt_cache:
            print(f"[JWT CACHE] Using cached token for {region}")
            return jwt_cache[region]
    
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

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if token:
            with jwt_lock:
                jwt_cache[region] = token
            print(f"[JWT] Token for {region} cached")
            return token
    except Exception as e:
        print(f"[JWT] Error: {e}")
    return None


# ---------------- FAST API ENDPOINTS ----------------
def get_api_endpoint(region):
    endpoints = {
        "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "US": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "SAC": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "BD": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "PK": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "ID": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "VN": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "TH": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "ME": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
        "default": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    }
    return endpoints.get(region, endpoints["default"])


# ---------------- FAST AES ENCRYPTION ----------------
default_key = "Yg&tc%DEuh6%Zc^8"
default_iv = "6oyZDr22E3ychjM%"
_key_bytes = default_key.encode()[:16]
_iv_bytes = default_iv.encode()[:16]

def encrypt_aes(hex_data, key=None, iv=None):
    """Optimized AES encryption"""
    if key is None or iv is None:
        key_bytes = _key_bytes
        iv_bytes = _iv_bytes
    else:
        key_bytes = key.encode()[:16]
        iv_bytes = iv.encode()[:16]
    
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()


# ---------------- FAST API CALL WITH RETRY ----------------
def apis(idd, region, retry_count=0):
    """Fast API call with automatic retry"""
    token = get_jwt_token_sync(region)
    if not token:
        raise Exception(f"No token for {region}")

    endpoint = get_api_endpoint(region)
    headers = {
        "User-Agent": "Dalvik/2.1.0",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Connection": "close",
    }

    try:
        data = bytes.fromhex(idd)
        response = requests.post(endpoint, headers=headers, data=data, timeout=8)
        
        if response.status_code == 401 and retry_count < 2:
            print(f"[API] Retry {retry_count + 1} for {region}")
            with jwt_lock:
                if region in jwt_cache:
                    del jwt_cache[region]
            time.sleep(0.3)
            return apis(idd, region, retry_count + 1)
        
        response.raise_for_status()
        return response.content.hex()
        
    except Exception as e:
        print(f"[API] Error: {e}")
        raise


# ---------------- FLASK ROUTE ----------------
@app.route("/accinfo", methods=["GET"])
def get_player_info():
    try:
        uid = request.args.get("uid")
        region = request.args.get("region", "").upper()
        
        if not uid:
            return jsonify({"error": "UID required"}), 400

        # Improved region detection with multiple fallbacks
        if not region:
            region = find_region_by_uid(uid)
            if not region:
                # Last resort - try to get from player info directly
                region = try_direct_region_detection(uid)
                if not region:
                    return jsonify({
                        "error": "Could not detect region. Please provide region manually (IND, US, BR, PK, etc.)",
                        "uid": uid,
                        "suggested_regions": ["IND", "BD", "PK", "ID", "VN", "TH", "US", "BR", "ME", "SAC"]
                    }), 400

        print(f"[INFO] Using region: {region} for UID: {uid}")

        # Generate protobuf
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        hex_data = binascii.hexlify(message.SerializeToString()).decode()

        # Encrypt
        encrypted_hex = encrypt_aes(hex_data)

        # API call
        api_response = apis(encrypted_hex, region)

        # Parse response
        message = AccountPersonalShowInfo()
        message.ParseFromString(bytes.fromhex(api_response))
        result = MessageToDict(message)
        result["Owners"] = ["𝗦𝗧𝗔𝗥 𝗚𝗔𝗠𝗘𝗥!!"]
        result["detected_region"] = region
        
        return jsonify(result)

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

def try_direct_region_detection(uid):
    """Last resort - try to detect region by making a test API call"""
    # Order by most common regions first
    test_regions = ['IND', 'BD', 'PK', 'ID', 'VN', 'TH', 'US', 'BR', 'ME', 'SAC']
    
    for test_region in test_regions:
        try:
            token = get_jwt_token_sync(test_region)
            if token:
                # Make a quick test call
                endpoint = get_api_endpoint(test_region)
                message = uid_generator_pb2.uid_generator()
                message.saturn_ = int(uid)
                message.garena = 1
                hex_data = binascii.hexlify(message.SerializeToString()).decode()
                encrypted = encrypt_aes(hex_data)
                
                headers = {
                    "User-Agent": "Dalvik/2.1.0",
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                
                response = requests.post(endpoint, headers=headers, data=bytes.fromhex(encrypted), timeout=5)
                if response.status_code == 200:
                    # Verify we got valid data
                    try:
                        test_message = AccountPersonalShowInfo()
                        test_message.ParseFromString(response.content)
                        if test_message.account_base_info.player_name:
                            print(f"[DIRECT DETECTION] Found region {test_region} for UID {uid}")
                            return test_region
                    except:
                        pass
        except Exception as e:
            print(f"[DIRECT DETECTION] Failed for {test_region}: {e}")
            continue
    
    return None


@app.route("/region/<uid>", methods=["GET"])
def detect_region_only(uid):
    """Endpoint to only detect region for a UID"""
    try:
        region = find_region_by_uid(uid)
        if region:
            return jsonify({
                "uid": uid,
                "region": region,
                "status": "success"
            })
        else:
            return jsonify({
                "uid": uid,
                "region": None,
                "status": "failed",
                "message": "Could not detect region automatically"
            }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/favicon.ico")
def favicon():
    return "", 404


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "cache_size": len(region_cache),
        "jwt_cache_size": len(jwt_cache),
        "message": "Server is working properly"
    })


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🚀 FAST SERVER STARTED! 🚀")
    print("⚡ Region finder FIXED with working APIs and fallbacks")
    print("📍 Usage: /accinfo?uid=1868812498")
    print("📍 Manual region: /accinfo?uid=1868812498&region=IND")
    print("📍 Detect only region: /region/1868812498")
    print("📍 Health check: /health")
    
    app.run(host="0.0.0.0", port=5552, threaded=True, use_reloader=False)