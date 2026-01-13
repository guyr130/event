# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import requests
from datetime import datetime
import json

app = Flask(__name__)

# ======================
# GOOGLE APPS SCRIPT URL  (החדש שלך)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxYOTETwFoJXbFHxNUwh3-AbwUsdnQ680194wn8svCFHE7c9zFreRI9hQhcDrPsAqM1/exec"


# ======================
# CONFIRM – בדיקת חיים
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")
    event_id = request.args.get("event_id")

    return f"""
    OK<br>
    family_id = {family_id}<br>
    event_id = {event_id}
    """


# ======================
# SUBMIT → שולח ל-Google Sheet
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    print("=== SUBMIT RECEIVED ===")
    print(data)

    # הוספת זמן אם לא הגיע מהקליינט
    if not data.get("timestamp"):
        data["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        print("Sending to Google Apps Script:")
        print(GOOGLE_SHEETS_WEBAPP_URL)

        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data,              # חשוב: json= ולא data=
            timeout=15
        )

        print("=== GOOGLE SCRIPT RESPONSE ===")
        print("Status:", r.status_code)
        print("Body:", r.text)

        return jsonify({
            "success": True,
            "google_status": r.status_code,
            "google_body": r.text
        })

    except Exception as e:
        print("=== ERROR SENDING TO GOOGLE SCRIPT ===")
        print(e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ======================
# THANKS – בדיקה בלבד
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")

    return f"""
    תודה!<br>
    סטטוס: {status}<br>
    כמות: {qty}
    """


# ======================
# HEALTH CHECK
# ======================
@app.route("/")
def home():
    return "Server is alive"


# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
