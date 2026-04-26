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

# ---------------- IMPROVED REGION FINDER (With Retry & Multiple APIs) ----------------
region_cache = {}
region_cache_lock = threading.Lock()

def find_region_by_uid(uid):
    """Fetch region using multiple APIs with retry logic"""
    
    # Check cache first
    with region_cache_lock:
        if uid in region_cache:
            print(f"[REGION CACHE] Hit for UID: {uid} -> {region_cache[uid]}")
            return region_cache[uid]
    
    print(f"[REGION FINDER] Searching region for UID: {uid}")
    
    # Multiple API endpoints for redundancy
    apis_to_try = [
        # Primary API
        {
            "url": "https://topup.pk/api/auth/player_id_login",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15; RMX5070) AppleWebKit/537.36",
                "Origin": "https://topup.pk",
                "Referer": "https://topup.pk/",
                "Connection": "close",
            },
            "payload": {"app_id": 100067, "login_id": str(uid)},
            "region_path": "region"
        },
        # Backup API 1
        {
            "url": "https://api.duniagames.co.id/api/ff/check_nickname",
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            "payload": {"nickname": str(uid)},
            "region_path": "data.region"
        },
        # Backup API 2 - Direct Garena endpoint
        {
            "url": f"https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
            "headers": {
                "User-Agent": "Dalvik/2.1.0",
            },
            "payload": None,  # Will try different approach
            "region_path": None
        }
    ]
    
    # Try each API with retry
    for api_index, api in enumerate(apis_to_try):
        for attempt in range(3):  # 3 attempts per API
            try:
                print(f"[REGION FINDER] Trying API {api_index + 1}, attempt {attempt + 1}")
                
                if api["url"] == "https://client.ind.freefiremobile.com/GetPlayerPersonalShow":
                    # Different approach for Garena API
                    response = requests.get(api["url"], timeout=5)
                    if response.status_code == 200:
                        # Check response headers for region
                        region = detect_region_from_headers(response.headers)
                        if region:
                            with region_cache_lock:
                                region_cache[uid] = region
                            print(f"[REGION FOUND] UID {uid} -> {region} (via Garena API)")
                            return region
                else:
                    # Normal POST request
                    response = requests.post(
                        api["url"],
                        headers=api["headers"],
                        json=api["payload"],
                        timeout=8
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        region = extract_region_from_response(data, api["region_path"])
                        if region:
                            with region_cache_lock:
                                region_cache[uid] = region
                            print(f"[REGION FOUND] UID {uid} -> {region} (via API {api_index + 1})")
                            return region
                        
            except Exception as e:
                print(f"[REGION FINDER] API {api_index + 1}, attempt {attempt + 1} failed: {e}")
            
            # Wait before retry
            if attempt < 2:
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

def extract_region_from_response(data, path):
    """Extract region from response data using path"""
    try:
        if not path:
            # Try common patterns
            if isinstance(data, dict):
                # Direct region field
                if "region" in data:
                    region = data["region"]
                    return region.upper() if region else None
                # Check in data object
                if "data" in data and isinstance(data["data"], dict):
                    if "region" in data["data"]:
                        region = data["data"]["region"]
                        return region.upper() if region else None
                # Check in result
                if "result" in data and isinstance(data["result"], dict):
                    if "region" in data["result"]:
                        region = data["result"]["region"]
                        return region.upper() if region else None
        else:
            # Navigate using path
            parts = path.split('.')
            current = data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            if current:
                return str(current).upper()
    except Exception:
        pass
    return None

def detect_region_from_headers(headers):
    """Detect region from response headers"""
    # Check for region in headers
    region_headers = ['X-Region', 'CF-Ray', 'Server', 'X-Server']
    for header in region_headers:
        if header in headers:
            value = headers[header]
            if 'ind' in value.lower():
                return 'IND'
            elif 'us' in value.lower() or 'na' in value.lower():
                return 'US'
            elif 'br' in value.lower():
                return 'BR'
            elif 'sg' in value.lower():
                return 'SAC'
    return None

def detect_region_by_pattern(uid):
    """Detect region based on UID pattern (fallback method)"""
    uid_str = str(uid)
    
    # Common region patterns
    patterns = {
        'IND': ['1', '2', '3', '4', '5', '6', '7', '8'],  # India UID patterns
        'BD': ['9', '10', '11', '12'],  # Bangladesh
        'ID': ['13', '14', '15', '16'],  # Indonesia
        'PK': ['17', '18', '19', '20'],  # Pakistan
        'BR': ['21', '22', '23'],  # Brazil
        'US': ['24', '25', '26'],  # USA
        'VN': ['27', '28', '29'],  # Vietnam
        'TH': ['30', '31', '32'],  # Thailand
        'ME': ['33', '34', '35'],  # Middle East
        'SAC': ['36', '37', '38'],  # South America Central
    }
    
    # Check first few digits
    prefix = uid_str[:2] if len(uid_str) >= 2 else uid_str[:1]
    
    for region, prefixes in patterns.items():
        if prefix in prefixes or any(uid_str.startswith(p) for p in prefixes):
            print(f"[PATTERN DETECTION] UID {uid} matches pattern for {region}")
            return region
    
    # Default to IND if pattern not found (most common)
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
                        "uid": uid
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
    test_regions = ['IND', 'BD', 'PK', 'ID', 'VN', 'TH', 'US', 'BR']
    
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
                    print(f"[DIRECT DETECTION] Found region {test_region} for UID {uid}")
                    return test_region
        except:
            continue
    
    return None


@app.route("/favicon.ico")
def favicon():
    return "", 404


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🚀 FAST SERVER STARTED! 🚀")
    print("⚡ Region finder FIXED with multiple APIs and fallbacks")
    print("📍 Usage: /accinfo?uid=1868812498")
    print("📍 Manual region: /accinfo?uid=1868812498&region=IND")
    
    app.run(host="0.0.0.0", port=5552, threaded=True, use_reloader=False)