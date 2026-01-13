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
IDEMPOTENCY_WINDOW = 15  # seconds


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

    if not event_id or not family_id or status not in ("yes", "no"):
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    print("=== SUBMIT ===", event_id, family_id, status, tickets)

    # ===== IDEMPOTENCY CHECK =====
    if is_duplicate(event_id, family_id, status, tickets):
        print("⚠ DUPLICATE REQUEST IGNORED")
        return jsonify({"success": True, "duplicate": True})

    # ===== Google Apps Script LOG =====
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

    try:
        print("Sending to Apps Script:", sheets_payload)

        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=sheets_payload,   # 🔥 השינוי הקריטי – json= ולא data=
            timeout=12
        )

        print("GOOGLE STATUS:", r.status_code)
        print("GOOGLE RESPONSE:", r.text)

    except Exception as e:
        print("Sheets error:", e)

    # ===== Zebra UPDATE =====
    a_c = "אישרו" if status == "yes" else "ביטלו"
    no_arive = tickets if status == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{a_c}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{no_arive}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        z = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15
        )
        print("ZEBRA STATUS:", z.status_code, z.text[:200])
    except Exception as e:
        print("Zebra error:", e)

    return jsonify({"success": True})


# ======================
# THANKS PAGE
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty", "0")
    event_id = request.args.get("event_id", "")
    family_id = request.args.get("family_id", "")
    return render_template("thanks.html", status=status, qty=qty, event_id=event_id, family_id=family_id)


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
