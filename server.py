# -*- coding: utf-8 -*-
from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "HOME OK V2"

@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()
    return f"DEBUG OK | family_id=[{family_id}] | event_id=[{event_id}]"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
