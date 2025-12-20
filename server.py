from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime

app = Flask(__name__)

GOOGLE_SHEETS_WEBAPP_URL = "https://PUT_REAL_URL_HERE"

ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "20/12/2025"


@app.route("/")
def home():
    return "OK"


@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    # 🔴 חשוב – ברירת מחדל כדי לא לקרוס
    tickets = 5

    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id,
        tickets=tickets
    )


@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    event_id = data["event_id"]
    family_id = data["family_id"]
    status = data["status"]
    tickets = int(data["tickets"])

    # ===== Google Sheets – נשאר כמו שהיה =====
    try:
        requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json={
                "event_id": event_id,
                "family_id": family_id,
                "status": status,
                "tickets": tickets,
                "ts": datetime.now().isoformat()
            },
            timeout=5
        )
    except Exception as e:
        print("Sheets ERROR:", e)

    # ===== Zebra – שתילה בטוחה =====
    zebra_status = "אישרו" if status == "yes" else "ביטלו"
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
        r = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=5
        )
        print("Zebra:", r.text)
    except Exception as e:
        print("Zebra ERROR:", e)

    return jsonify(success=True)


@app.route("/thanks")
def thanks():
    return "תודה! העדכון נקלט"
