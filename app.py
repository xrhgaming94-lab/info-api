import base64
import binascii
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ---------------- ALL REGIONS ----------------
ALL_REGIONS = ["IND", "SG", "ID", "BR", "TH", "VN", "TW", "RU", "ME", "PK", "BD"]

# ---------------- JWT ENDPOINTS FOR EACH REGION ----------------
JWT_ENDPOINTS = {
    "IND": "http://star-jwt-gen.vercel.app/token?uid=4569404695&password=RAGHAVLIKESBOT_RAGHAV_2THCG",
    "SG": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
    "ID": "http://star-jwt-gen.vercel.app/token?uid=4708244360&password=IDOY-QSKOPFJYU-SG",
    "BR": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
    "TH": "http://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
    "VN": "http://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
    "TW": "http://star-jwt-gen.vercel.app/token?uid=4514032809&password=F56CBAFE83A2161F3DE643FD2321C1223B35A6144D08F26A06D405A7A69A149E",
    "RU": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=CCBD38AAC5A1FA5807FD683B6DD0EE6C5F4F7447DD51C6D30062CD425B10E493",
    "ME": "http://star-jwt-gen.vercel.app/token?uid=4724874406&password=CCBD38AAC5A1FA5807FD683B6DD0EE6C5F4F7447DD51C6D30062CD425B10E493",
    "PK": "http://star-jwt-gen.vercel.app/token?uid=4680926895&password=gamer-07G3N3MND-X64",
    "BD": "https://star-jwt-gen.vercel.app/token?uid=4331389599&password=Sumon523022_BREXX_4KQT9",
}

# ---------------- API ENDPOINTS FOR EACH REGION ----------------
API_ENDPOINTS = {
    "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
    "SG": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
    "ID": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
    "TH": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "VN": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "TW": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
    "RU": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "ME": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "PK": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
    "BD": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow",
}

# ---------------- JWT HANDLING ----------------
def get_jwt_token(region):
    """Get JWT token for a region with caching"""
    # Check cache
    with jwt_lock:
        if region in jwt_cache:
            token_data = jwt_cache[region]
            if time.time() - token_data['time'] < 300:  # 5 minutes cache
                return token_data['token']
    
    url = JWT_ENDPOINTS.get(region)
    if not url:
        return None
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            if token:
                with jwt_lock:
                    jwt_cache[region] = {'token': token, 'time': time.time()}
                return token
    except Exception as e:
        print(f"[JWT] Error for {region}: {e}")
    return None

# ---------------- AES ENCRYPTION ----------------
default_key = "Yg&tc%DEuh6%Zc^8"
default_iv = "6oyZDr22E3ychjM%"

def encrypt_aes(hex_data, key=default_key, iv=default_iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

# ---------------- CHECK SINGLE REGION ----------------
def check_region(uid, region, encrypted_hex, result_dict):
    """Check a single region for the UID"""
    try:
        print(f"[CHECKING] Region: {region}")
        
        # Get JWT token
        token = get_jwt_token(region)
        if not token:
            print(f"[FAILED] No token for {region}")
            return None
        
        # Make API call
        endpoint = API_ENDPOINTS.get(region)
        headers = {
            "User-Agent": "Dalvik/2.1.0",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "close",
        }
        
        response = requests.post(
            endpoint, 
            headers=headers, 
            data=bytes.fromhex(encrypted_hex), 
            timeout=8
        )
        
        if response.status_code == 200:
            # Parse response
            message = AccountPersonalShowInfo()
            message.ParseFromString(bytes.fromhex(response.content.hex()))
            result = MessageToDict(message)
            
            # Check if valid player data received
            if result.get('person_show_info', {}).get('nick_name'):
                print(f"[SUCCESS] Found in {region} region!")
                result['region'] = region
                result['detected_region'] = region
                result['Owners'] = ["𝗦𝗧𝗔𝗥 𝗚𝗔𝗠𝗘𝗥!!"]
                result_dict['success'] = True
                result_dict['data'] = result
                return region
        else:
            print(f"[FAILED] {region} - Status: {response.status_code}")
            
    except Exception as e:
        print(f"[FAILED] {region} - Error: {str(e)[:50]}")
    
    return None

# ---------------- FLASK ROUTE ----------------
@app.route("/accinfo", methods=["GET"])
def get_player_info():
    try:
        uid = request.args.get("uid")
        custom_key = request.args.get("key", default_key)
        custom_iv = request.args.get("iv", default_iv)
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400
        
        print(f"\n{'='*50}")
        print(f"[START] Searching for UID: {uid}")
        print(f"[INFO] Checking all {len(ALL_REGIONS)} regions in parallel")
        print(f"{'='*50}")
        
        # Generate protobuf once
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        protobuf_data = message.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()
        
        # Encrypt once
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)
        
        # Check all regions in parallel
        result_holder = {'success': False, 'data': None}
        
        with ThreadPoolExecutor(max_workers=len(ALL_REGIONS)) as executor:
            futures = {
                executor.submit(check_region, uid, region, encrypted_hex, result_holder): region 
                for region in ALL_REGIONS
            }
            
            # Wait for first successful response
            for future in as_completed(futures):
                region = futures[future]
                try:
                    result = future.result(timeout=10)
                    if result_holder['success']:
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        print(f"\n{'='*50}")
                        print(f"[DONE] Found in region: {region}")
                        print(f"{'='*50}\n")
                        return jsonify(result_holder['data'])
                except Exception as e:
                    print(f"[ERROR] {region} failed: {e}")
                    continue
        
        # If no region found
        print(f"\n{'='*50}")
        print(f"[FAILED] No region found for UID: {uid}")
        print(f"{'='*50}\n")
        return jsonify({
            "error": "Player not found in any region",
            "uid": uid,
            "regions_checked": ALL_REGIONS
        }), 404
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/favicon.ico")
def favicon():
    return "", 404

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("="*50)
    print("🔥 ULTRA FAST REGION FINDER 🔥")
    print("="*50)
    print(f"📍 Total Regions: {len(ALL_REGIONS)}")
    print(f"📍 Regions: {', '.join(ALL_REGIONS)}")
    print("📍 Working: Checks all regions in PARALLEL")
    print("📍 Returns: First successful response")
    print("="*50)
    print("\n🚀 Server Started!")
    print("📌 Usage: /accinfo?uid=1868812498")
    print("="*50)
    
    app.run(host="0.0.0.0", port=5552, threaded=True, use_reloader=False)