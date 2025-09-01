import os, requests, json
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

BIN_ID = os.environ.get("BIN_ID")      # JSONBin bin ID
SECRET_KEY = os.environ.get("BIN_KEY") # JSONBin secret key

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def get_memory():
    r = requests.get(f"{JSONBIN_URL}/latest", headers={"X-Master-Key": SECRET_KEY})
    data = r.json()
    return data["record"].get("memory", [])

def save_memory(memory_list):
    r = requests.put(JSONBIN_URL, headers={"X-Master-Key": SECRET_KEY, "Content-Type":"application/json"}, 
                     data=json.dumps({"memory": memory_list}))
    return r.ok

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/learn", methods=["POST"])
def learn():
    data = request.json
    text = data.get("text","").strip()
    if not text: return jsonify({"ok":False,"error":"empty"}),400
    mem = get_memory()
    mem.append(text)
    save_memory(mem)
    return jsonify({"ok":True,"saved":text})

@app.route("/reply", methods=["POST"])
def reply():
    data = request.json
    prompt = data.get("prompt","").strip()
    mem = get_memory()
    if not mem:
        return jsonify({"reply":"I don't know yet. Teach me first!"})
    best = max(mem, key=lambda x: len(set(x.split()) & set(prompt.split())))
    return jsonify({"reply": best})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
