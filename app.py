import os, json, time
from flask import Flask, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from difflib import SequenceMatcher

# Config (set these in Render env)
GOOGLE_DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # raw JSON string
PORT = int(os.environ.get("PORT", 5000))
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")  # optional; if set, /learn requires it

if not GOOGLE_DOC_ID or not SA_JSON:
    raise RuntimeError("Set GOOGLE_DOC_ID and GOOGLE_SERVICE_ACCOUNT_JSON env vars before starting.")

# Google Docs client
sa_info = json.loads(SA_JSON)
SCOPES = ["https://www.googleapis.com/auth/documents"]
credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
docs_service = build("docs", "v1", credentials=credentials, cache_discovery=False)

app = Flask(__name__, static_folder="static", static_url_path="/static")
memory = []

def load_memory_from_doc():
    global memory
    try:
        doc = docs_service.documents().get(documentId=GOOGLE_DOC_ID).execute()
        body = doc.get("body", {}).get("content", [])
        text = []
        for el in body:
            p = el.get("paragraph")
            if not p: continue
            for elem in p.get("elements", []):
                seg = elem.get("textRun", {}).get("content")
                if seg:
                    text.append(seg)
        full = "".join(text).strip()
        memory = [line for line in full.splitlines() if line.strip()]
        app.logger.info(f"Loaded {len(memory)} entries from Google Doc")
    except Exception as e:
        app.logger.warning(f"Could not load memory from doc: {e}")
        memory = []

def append_to_doc(text_to_append):
    doc = docs_service.documents().get(documentId=GOOGLE_DOC_ID).execute()
    body = doc.get("body", {}).get("content", [])
    try:
        end_index = body[-1]["endIndex"]
    except Exception:
        end_index = 1
    payload_text = ("\n" + text_to_append + "\n")
    requests = [{"insertText": {"location": {"index": end_index}, "text": payload_text}}]
    docs_service.documents().batchUpdate(documentId=GOOGLE_DOC_ID, body={"requests": requests}).execute()

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "memory_count": len(memory)})

@app.route("/learn", methods=["POST"])
def learn():
    if AUTH_TOKEN:
        token = request.headers.get("Authorization", "")
        if token != f"Bearer {AUTH_TOKEN}":
            return jsonify({"ok": False, "error": "unauthorized"}), 401

    payload = request.get_json(force=True)
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty text"}), 400

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    entry = f"[{ts}] {text}"
    try:
        append_to_doc(entry)
        memory.append(entry)
        return jsonify({"ok": True, "saved": entry})
    except Exception as e:
        app.logger.exception("Failed to append to Google Doc")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/reply", methods=["POST"])
def reply():
    payload = request.get_json(force=True)
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "empty prompt"}), 400

    if not memory:
        return jsonify({"ok": True, "reply": "I don't know yet — teach me using learn mode."})

    best_score = 0.0
    best_entry = None
    for entry in memory:
        content = entry.split("] ", 1)[-1]
        s = similarity(prompt, content)
        if s > best_score:
            best_score = s
            best_entry = content

    if best_score < 0.25:
        reply_text = f"I didn't find a close match. I remember: \"{memory[-1].split('] ',1)[-1]}\""
    else:
        reply_text = best_entry

    return jsonify({"ok": True, "reply": reply_text, "score": best_score})

if __name__ == "__main__":
    load_memory_from_doc()
    app.run(host="0.0.0.0", port=PORT)
