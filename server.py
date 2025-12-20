from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================

GOOGLE_SHEETS_WEBAPP_URL = ""  # אפשר להשאיר ריק זמנית

ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "20/12/2025"


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK – server is running"


# ======================
# CONFIRM PAGE
# ======================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    # ✅ ערך ברירת מחדל כדי ש-Jinja לא יקרוס
    tickets = 5

    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id,
        tickets=tickets
    )


# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")  # yes / no
    tickets = int(data.get("tickets", 0))

    # ======================
    # 1️⃣ GOOGLE SHEETS (לא חובה)
    # ======================
    if GOOGLE_SHEETS_WEBAPP_URL:
        try:
            requests.post(
                GOOGLE_SHEETS_WEBAPP_URL,
                json={
                    "timestamp": datetime.now().isoformat(),
                    "event_id": event_id,
                    "family_id": family_id,
                    "status": status,
                    "tickets": tickets,
                },
                timeout=10
            )
        except Exception as e:
            print("Sheets ERROR:", e)

    # ======================
    # 2️⃣ ZEBRA UPDATE
    # ======================
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
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=10
        )
        print("Zebra OK:", zr.text)
    except Exception as e:
        print("Zebra ERROR:", e)

    return jsonify({"success": True})


# ======================
# THANK YOU PAGE
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty", "0")
    return f"תודה! סטטוס: {status}, כמות: {qty}"


# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
