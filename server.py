from flask import Flask, request, render_template, redirect
import requests
import datetime
from zebra_api import update_askev_attendance

app = Flask(__name__)

GOOGLE_SHEET_WEBHOOK = "https://script.google.com/macros/s/XXXX/exec"

@app.route("/confirm")
def confirm():
    return render_template(
        "confirm.html",
        event_id=request.args.get("event_id"),
        zebra_family_id=request.args.get("family_id"),
        family_name="משפחת ביטון",
        tickets=2,
        event_name="אירוע בדיקה",
        event_date="17/12/2025",
        location="ירושלים"
    )

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()

    event_id = data["event_id"]
    family_id = data["family_id"]
    status = data["status"]
    tickets = int(data.get("tickets", 0))

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": tickets
    }

    # Google Sheets
    try:
        r = requests.post(GOOGLE_SHEET_WEBHOOK, json=payload, timeout=5)
        print("Sheets:", r.status_code, r.text)
    except Exception as e:
        print("Sheets error:", e)

    # Zebra
    try:
        update_askev_attendance(
            family_id=family_id,
            event_id=event_id,
            status=status,
            tickets=tickets
        )
    except Exception as e:
        print("Zebra error:", e)

    return redirect(f"/thanks?status={status}&qty={tickets}")

@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )

@app.route("/")
def root():
    return "OK"
