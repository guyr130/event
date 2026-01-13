# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import time

app = Flask(__name__)

# ======================
# GOOGLE APPS SCRIPT (LOG)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyYTuGyUg1YLJyclKj31X5r1Aa4rcqo0oMHcsoR2KQKv7KKAFSu65lf7B1o8UM771oy/exec"

# ======================
# TEST CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")
    event_id = request.args.get("event_id")

    if not family_id:
        return "Missing family_id", 400

    # בדיקה פשוטה בלבד – בלי זברה, בלי לוגיקה
    return f"""
    OK<br>
    family_id = {family_id}<br>
    event_id = {event_id}
    """

# ======================
# SUBMIT – בדיקת לוג בלבד
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    print("=== SUBMIT RECEIVED ===")
    print(data)

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data,
            timeout=12
        )
        print("GOOGLE STATUS:", r.status_code)
        print("GOOGLE RESPONSE:", r.text)
    except Exception as e:
        print("Sheets error:", e)

    return jsonify({"success": True})


@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
