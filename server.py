from zebra_api import update_askev_attendance
from flask import Flask, request, render_template, jsonify
import requests
import datetime

app = Flask(__name__)

# =========================
# CONFIG
# =========================
GOOGLE_SHEET_WEBHOOK = "PASTE_HERE_YOUR_SHEETS_WEBHOOK_URL"

# =========================
# CONFIRM PAGE
# =========================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    return render_template(
        "confirm.html",
        event_id=event_id,
        zebra_family_id=family_id,
        family_name="משפחה לדוגמה",
        tickets=2,
        event_name="אירוע בדיקה",
        event_date="17/12/2025",
        location="ירושלים"
    )

# =========================
# SUBMIT
# =========================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event_id": data.get("event_id"),
        "family_id": data.get("family_id"),
        "status": data.get("status"),
        "tickets": data.get("tickets"),
        "user_agent": request.headers.get("User-Agent"),
        "ip": request.remote_addr
    }

    # ---- SEND TO GOOGLE SHEETS ----
    try:
        requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print("Sheets error:", e)

    return jsonify({"ok": True})

# =========================
# THANK YOU PAGE
# =========================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")

    return render_template(
        "thanks.html",
        status=status,
        qty=qty
    )

# =========================
# ROOT (health)
# =========================
@app.route("/")
def root():
    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
