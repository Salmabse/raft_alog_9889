from flask import Flask, request, jsonify
import os
import threading
import time

from raft import RaftNode

app = Flask(__name__)

NODE_ID = os.environ.get("NODE_ID", "1")
PORT = int(os.environ.get("PORT", "5000"))
PEERS_ENV = os.environ.get("PEERS", "")
PEERS = [p.strip() for p in PEERS_ENV.split(",") if p.strip()]

node = RaftNode(node_id=NODE_ID, peers=PEERS, port=PORT)

@app.route("/status", methods=["GET"])
def status():
    return jsonify(node.get_state())

@app.route("/request_vote", methods=["POST"])
def request_vote():
    data = request.get_json()
    resp = node.handle_request_vote(data)
    return jsonify(resp)

@app.route("/append_entries", methods=["POST"])
def append_entries():
    data = request.get_json()
    resp = node.handle_append_entries(data)
    return jsonify(resp)

@app.route("/client_command", methods=["POST"])
def client_command():
    data = request.get_json()
    cmd = data.get("command")
    res = node.client_command(cmd)
    if res.get("success"):
        return jsonify({"success": True, "index": res.get("index")})
    else:
        # redirect info: find current leader (very simple: try to detect leader by querying peers)
        for p in node.peers:
            try:
                r = requests.get(f"http://{p}/status", timeout=0.8)
                st = r.json()
                if st.get("state") == "leader":
                    return jsonify({"success": False, "redirect": f"http://{p}/client_command"})
            except Exception:
                pass
        return jsonify({"success": False, "message": "no leader known"})

if __name__ == "__main__":
    print(f"Starting node {NODE_ID} on port {PORT} peers={PEERS}")
    app.run(host="0.0.0.0", port=PORT)
