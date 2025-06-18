from flask import Flask, request, jsonify
import uuid
import datetime
import re
import netifaces

# 获取 en0 网卡的 IPv4 地址
# Get the ip address of en0 interface
def get_en0_ipv4():
    try:
        interfaces = netifaces.ifaddresses("en0")
        ipv4_info = interfaces.get(netifaces.AF_INET)
        if ipv4_info:
            return ipv4_info[0]["addr"]
    except Exception as e:
        print("Fail to get IP of en0:", e)
    return "192.168.31.12"  # fallback 默认值

en0_ipv4 = get_en0_ipv4()

app = Flask(__name__)

# 模拟配置 Simulate F5 info
CONFIG = {
    "f5": {
        "username": "admin",
        "password": "admin",
        "host": "127.0.0.1",
        "port": 8443
    }
}

# Set the store of token
tokens_db = {}

def generate_token(username):
    token = uuid.uuid4().hex.upper()
    now = datetime.datetime.now()
    tokens_db[token] = {
        "name": token,
        "token": token,
        "userName": username,
        "timeout": 1200,
        "startTime": now.isoformat(),
        "expirationMicros": int((now + datetime.timedelta(seconds=1200)).timestamp() * 1_000_000)
    }
    return tokens_db[token]

@app.route("/mgmt/shared/authn/login", methods=["POST"])
def login():
    data = request.get_json()
    if data["username"] == CONFIG["f5"]["username"] and data["password"] == CONFIG["f5"]["password"]:
        token_obj = generate_token(data["username"])
        return jsonify({
            "username": data["username"],
            "loginProviderName": "tmos",
            "token": token_obj,
            "generation": 0,
            "lastUpdateMicros": 0
        }), 200
    else:
        return jsonify({"error": "Unauthorized"}), 401

@app.route("/mgmt/shared/authz/tokens", methods=["GET"])
def verify_token():
    token = request.headers.get("X-F5-Auth-Token")
    if token in tokens_db:
        # 返回所有 token（模拟旧 token 也存在）
        # Return all tokens
        return jsonify({
            "items": list(tokens_db.values()),
            "generation": 259,
            "kind": "shared:authz:tokens:authtokencollectionstate"
        }), 200
    else:
        return jsonify({"error": "Invalid token"}), 401

@app.route("/mgmt/shared/authz/tokens/<token_name>", methods=["PATCH"])
def update_token(token_name):
    auth_token = request.headers.get("X-F5-Auth-Token")
    if auth_token not in tokens_db:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if token_name in tokens_db:
        tokens_db[token_name]["timeout"] = int(data.get("timeout", 36000))
        now = datetime.datetime.now()
        tokens_db[token_name]["expirationMicros"] = int(
            (now + datetime.timedelta(seconds=tokens_db[token_name]["timeout"])).timestamp() * 1_000_000
        )
        return jsonify(tokens_db[token_name]), 200
    else:
        return jsonify({"error": "Token not found"}), 404

@app.route("/mgmt/tm/ltm/pool/<path:full_path>/members", methods=["GET"])
def get_pool_members(full_path):
    auth_token = request.headers.get("X-F5-Auth-Token")
    if auth_token not in tokens_db:
        return jsonify({"error": "Unauthorized"}), 401

    match = re.search(r"~(?P<partition>[^~]+)~(?P<pool_name>[^/]+)", full_path)
    if not match:
        return jsonify({"error": "Invalid pool path"}), 400

    partition = match.group("partition")
    pool_name = match.group("pool_name")

    # 动态模式开关：1 表示动态返回，0 表示始终返回完整列表
    # The switch, simulate the dynamic pool members, 0=off, 1=on
    DYNAMIC_MODE = 0

    if pool_name == "example_pool1":
        members = [
            {
                "name": "127.0.0.1:8001",
                "address": "127.0.0.1",
                "partition": partition,
                "fullPath": f"/{partition}/127.0.0.1:8001"
            },
            {
                "name": "127.0.0.1:8002",
                "address": "127.0.0.1",
                "partition": partition,
                "fullPath": f"/{partition}/127.0.0.1:8002"
            },
            {
                "name": "127.0.0.1:8003",
                "address": "127.0.0.1",
                "partition": partition,
                "fullPath": f"/{partition}/127.0.0.1:8003"
            }
        ]
    elif pool_name == "example_pool2":
        members = [
            {
                "name": f"{en0_ipv4}:8012",
                "address": en0_ipv4,
                "partition": partition,
                "fullPath": f"/{partition}/{en0_ipv4}:8012"
            },
            {
                "name": "{en0_ipv4}:8015",
                "address": en0_ipv4,
                "partition": partition,
                "fullPath": f"/{partition}/{en0_ipv4}:8015"
            },
            {
                "name": f"{en0_ipv4}:8010",
                "address": en0_ipv4,
                "partition": partition,
                "fullPath": f"/{partition}/{en0_ipv4}:8010"
            }
        ]
    else:
        return jsonify({"items": []})
    
    
    if DYNAMIC_MODE == 1:
        import random
        members = random.sample(members, k=random.randint(0, len(members)))

    return jsonify({
        "kind": "tm:ltm:pool:members:memberscollectionstate",
        "selfLink": f"https://{CONFIG['f5']['host']}/mgmt/tm/ltm/pool/~{partition}~{pool_name}/members",
        "items": members
    }), 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=CONFIG["f5"]["port"],
        ssl_context=("cert.pem", "key.pem"),
        debug=True
    )
