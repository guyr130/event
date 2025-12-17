from flask import Flask, request, render_template, jsonify, redirect
import requests
import datetime
from zebra_api import update_askev_attendance

app = Flask(__name__)

# =========================
# CONFIG
# =========================
GOOGLE_SHEET_WEBHOOK = "https://script.google.com/macros/s/XXXXXXXX/exec"
# ⬆️ חובה להחליף ל־URL האמיתי שלך

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
        family_name="משפחת ביטון",
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

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")        # yes / no
    tickets = int(data.get("tickets", 0))

    approval_date = datetime.datetime.now().strftime("%d/%m/%Y")

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": tickets,
        "user_agent": request.headers.get("User-Agent"),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr)
    }

    # ---- GOOGLE SHEETS ----
    try:
        r = requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
        print("Sheets response:", r.status_code, r.text)
    except Exception as e:
        print("Sheets error:", e)

    # ---- ZEBRA ASKEV ----
    try:
        update_askev_attendance(
            family_id=family_id,
            event_id=event_id,
            status=status,
            tickets=tickets,
            approval_date=approval_date
        )
    except Exception as e:
        print("Zebra error:", e)

    return redirect(f"/thanks?status={status}&qty={tickets}")

# =========================
# THANK YOU PAGE
# =========================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )

# =========================
# ROOT (health)
# =========================
@app.route("/")
def root():
    return "OK"

# =========================
# RUN (local only)
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
