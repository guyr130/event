# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

# ======================
# GOOGLE APPS SCRIPT URL
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxYOTETwFoJXbFHxNUwh3-AbwUsdnQ680194wn8svCFHE7c9zFreRI9hQhcDrPsAqM1/exec"


# ======================
# CONFIRM  → מציג את הדף המעוצב
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")
    event_id = request.args.get("event_id")

    if not family_id:
        return "Missing family_id", 400

    # כרגע נתונים סטטיים לבדיקה
    # בהמשך יבואו מזברה
    return render_template(
        "confirm.html",
        family_id=family_id,
        family_name="כהן ישראלה וישראל",
        event_id=event_id or "22459",
        event_name="אור שמחה וגיפים באקסטרים",
        event_date="28/01/2026",
        event_time="09:00",
        location="צפון הנגב",
        tickets=2
    )


# ======================
# SUBMIT → שולח לשיט
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    print("=== SUBMIT RECEIVED ===")
    print(data)

    # הוספת חותמת זמן אם לא נשלחה
    if not data.get("timestamp"):
        data["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data,   # חשוב: שליחה כ־JSON
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
# THANKS → דף תודה
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    return render_template(
        "thanks.html",
        status=status,
        qty=qty,
        event_id=event_id,
        family_id=family_id
    )


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
