from flask import Flask, request, jsonify, send_from_directory
import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

app = Flask(__name__)

# Google Docs setup
DOC_ID = os.environ.get("DOC_ID")  # put your doc ID in Render env
SCOPES = ["https://www.googleapis.com/auth/documents"]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
docs_service = build("docs", "v1", credentials=creds)

mode = "learn"

def append_to_doc(text):
    requests = [
        {"insertText": {
            "location": {"index": 1},
            "text": f"{datetime.now()}: {text}\n"
        }}
    ]
    docs_service.documents().batchUpdate(
        documentId=DOC_ID, body={"requests": requests}
    ).execute()

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/set_mode", methods=["POST"])
def set_mode():
    global mode
    mode = request.json.get("mode", "learn")
    return jsonify({"status": "ok", "mode": mode})

@app.route("/message", methods=["POST"])
def message():
    global mode
    data = request.json
    text = data.get("text", "")
    if mode == "learn":
        append_to_doc(text)
        return jsonify({"reply": "Learning..."})
    else:
        return jsonify({"reply": f"You said: {text}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
