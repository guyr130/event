# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
import os
import requests
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================
GOOGLE_SHEETS_WEBAPP_URL = os.getenv("GOOGLE_SHEETS_WEBAPP_URL", "").strip()

ZEBRA_UPDATE_URL = os.getenv(
    "ZEBRA_UPDATE_URL",
    "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
).strip()

ZEBRA_USER = os.getenv("ZEBRA_USER", "IVAPP").strip()
ZEBRA_PASS = os.getenv("ZEBRA_PASS", "1q2w3e4r").strip()

# תאריך קבוע (כמו שעבד קודם)
FIXED_DATE = os.getenv("FIXED_DATE", "20/12/2025").strip()

# ======================
# 🔒 EVENT ID – שינוי יחיד
# ======================
EVENT_ID = "22459"

# ======================
# HELPERS
# ======================
def safe_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def post_to_google_sheets(payload: dict) -> tuple[bool, str]:
    if not GOOGLE_SHEETS_WEBAPP_URL or "PASTE_YOUR" in GOOGLE_SHEETS_WEBAPP_URL:
        return False, "GOOGLE_SHEETS_WEBAPP_URL not configured"

    try:
        r = requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=10)
        return (200 <= r.status_code < 300), f"status={r.status_code}"
    except Exception as e:
        return False, f"exception={e}"


def post_to_zebra_update(event_id: str, family_id: str, status: str, tickets: int) -> tuple[bool, str]:
    zebra_status = "אישרו" if status == "yes" else "ביטל"
    zebra_tickets = tickets if status == "yes" else 0

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

    <CUST_DETAILS>
    </CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{zebra_status}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        zr = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml,
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=15
        )
        return (200 <= zr.status_code < 300), zr.text
    except Exception as e:
        return False, f"exception={e}"


# ======================
# ROUTES
# ======================
@app.route("/")
def home():
    return "OK – server is running"


@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    if not family_id:
        return "Missing parameters", 400

    family_name = request.args.get("family_name", "משפחה").strip() or "משפחה"
    event_name = request.args.get("event_name", "אירוע").strip() or "אירוע"
    event_date = request.args.get("event_date", FIXED_DATE).strip() or FIXED_DATE
    location = request.args.get("location", "").strip()

    tickets = safe_int(request.args.get("tickets", "2"), default=2)
    if tickets < 1:
        tickets = 1

    return render_template(
        "confirm.html",
        event_id=EVENT_ID,
        family_id=family_id,
        family_name=family_name,
        event_name=event_name,
        event_date=event_date,
        location=location,
        tickets=tickets
    )


@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    family_id = str(data.get("family_id", "")).strip()
    status = str(data.get("status", "")).strip()
    tickets = safe_int(data.get("tickets", 0), default=0)

    # ===== GOOGLE SHEETS =====
    sheet_payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": EVENT_ID,
        "family_id": family_id,
        "status": status,
        "tickets": tickets,
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }

    sheets_ok, sheets_msg = post_to_google_sheets(sheet_payload)
    print("Sheets:", sheets_ok, sheets_msg)

    # ===== ZEBRA =====
    zebra_ok, zebra_resp = post_to_zebra_update(EVENT_ID, family_id, status, tickets)
    print("Zebra:", zebra_ok, zebra_resp)

    return jsonify({
        "success": True,
        "sheets_ok": sheets_ok,
        "zebra_ok": zebra_ok,
        "zebra_raw": zebra_resp[:5000]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
