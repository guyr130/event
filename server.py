# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
from datetime import datetime
import json

app = Flask(__name__)

# ======================
# GOOGLE APPS SCRIPT URL
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzIlUc9LX2SqXq6QdguAsd0BVvC8G-W6Wo1mpMasFWR5a-4U1ZJv326pRewci0xoXhx/exec"


# ======================
# CONFIRM (בדיקה פשוטה)
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
# SUBMIT → שולח לשיט
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    print("=== SUBMIT RECEIVED FROM CLIENT ===")
    print(data)

    # מוסיפים חותמת זמן אם לא נשלחה
    if not data.get("timestamp"):
        data["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        print("Sending to Google Sheets URL:")
        print(GOOGLE_SHEETS_WEBAPP_URL)

        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data,  # זה השינוי החשוב
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
# THANKS (בדיקה בלבד)
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
