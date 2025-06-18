from flask import Flask, request, jsonify
import uuid
import datetime
import re

app = Flask(__name__)

# 模拟配置
CONFIG = {
    "f5": {
        "username": "admin",
        "password": "admin",
        "host": "127.0.0.1",
        "port": 8443
    }
}

# 模拟 token 存储
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

    if pool_name == "example_pool1":
        items = [
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
        items = [
            {
                "name": "192.168.31.12:8012",
                "address": "192.168.31.12",
                "partition": partition,
                "fullPath": f"/{partition}/192.168.31.12:8012"
            },
            {
                "name": "192.168.31.12:8010",
                "address": "192.168.31.12",
                "partition": partition,
                "fullPath": f"/{partition}/192.168.31.12:8010"
            }
        ]
    else:
        items = []

    return jsonify({
        "kind": "tm:ltm:pool:members:memberscollectionstate",
        "selfLink": f"https://{CONFIG['f5']['host']}/mgmt/tm/ltm/pool/~{partition}~{pool_name}/members",
        "items": items
    }), 200

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=CONFIG["f5"]["port"],
        ssl_context=("cert.pem", "key.pem"),
        debug=True
    )
