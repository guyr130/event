# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import time

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "20/12/2025"
FIXED_TIME = "08:00"

# ======================
# GOOGLE APPS SCRIPT (LOG)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyYTuGyUg1YLJyclKj31X5r1Aa4rcqo0oMHcsoR2KQKv7KKAFSu65lf7B1o8UM771oy/exec"

# ======================
# MEMORY FOR IDEMPOTENCY
# ======================
recent_requests = {}
IDEMPOTENCY_WINDOW = 15


def is_duplicate(event_id, family_id, status, tickets):
    now = time.time()
    key = f"{event_id}|{family_id}|{status}|{tickets}"

    expired = [k for k, v in recent_requests.items() if now - v > IDEMPOTENCY_WINDOW]
    for k in expired:
        del recent_requests[k]

    if key in recent_requests:
        return True

    recent_requests[key] = now
    return False


# ======================
# ZEBRA GET EVENT
# ======================
def get_event_data(event_id: str):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
            <FIELDS>
                <ID></ID>
                <CO_NAME></CO_NAME>
            </FIELDS>
            <CON_FIELDS>
                <TOT_FFAM></TOT_FFAM>
                <PROV></PROV>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=15
    )

    tree = ET.fromstring(r.text)
    card = tree.find(".//CARD")
    if card is None:
        return None

    event = {
        "event_name": card.findtext(".//EV_N", "").strip(),
        "event_date": card.findtext(".//EV_D", "").strip(),
        "event_time": card.findtext(".//EVE_HOUR", "").strip() or FIXED_TIME,
        "location": card.findtext(".//EVE_LOC", "").strip(),
        "families": []
    }

    for el in card.findall(".//CONNECTIONS_CARDS/*"):
        if el.tag.startswith("CARD_CONNECTION_"):
            event["families"].append({
                "id": el.findtext("ID"),
                "family_name": el.findtext(".//CO_NAME", "").strip(),
                "tickets": int(el.findtext(".//TOT_FFAM", "0")),
                "approved": el.findtext(".//PROV", "0")
            })

    return event


# ======================
# CONFIRM PAGE
# ======================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    event = get_event_data(event_id)
    if not event:
        return "Event not found in Zebra", 404

    family = next((f for f in event["families"] if f["id"] == family_id), None)
    if not family:
        return "Family not connected to event", 404

    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id,
        family_name=family["family_name"],
        tickets=family["tickets"],
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["location"]
    )


# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = str(data.get("event_id") or "").strip()
    family_id = str(data.get("family_id") or "").strip()
    status = str(data.get("status") or "").strip()
    tickets = int(data.get("tickets", 0) or 0)

    family_name = (data.get("family_name") or "").strip()
    event_name = (data.get("event_name") or "").strip()

    print("=== SUBMIT ===", event_id, family_id, status, tickets)

    if is_duplicate(event_id, family_id, status, tickets):
        print("⚠ DUPLICATE IGNORED")
        return jsonify({"success": True, "duplicate": True})

    status_he = "אישרו" if status == "yes" else "ביטלו"
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    sheets_payload = {
        "timestamp": timestamp,
        "family_id": family_id,
        "family_name": family_name,
        "event_id": event_id,
        "event_name": event_name,
        "status": status_he,
        "tickets": tickets
    }

    # 🔥 כאן התיקון הקריטי
    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=sheets_payload,
            timeout=12
        )
        print("GOOGLE STATUS:", r.status_code, r.text)
    except Exception as e:
        print("Sheets error:", e)

    return jsonify({"success": True})


# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty", "0")
    return render_template("thanks.html", status=status, qty=qty)


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK – server is running"


# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
