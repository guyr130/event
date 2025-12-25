# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "20/12/2025"   # זמני
FIXED_TIME = "08:00"        # זמני

# ======================
# GOOGLE SHEETS (✔ מוכן)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbyK2wobbQUnN8hQ2HwL9sauJ4Nv8N3JpsRCdGGlrAY4KmEPnq2CUZFBaC_GZXJ7I3HT"
    "/exec"
)

# ======================
# GET EVENT DATA (ZEBRA)
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
        "event_date": card.findtext(".//EV_D", "").strip() or FIXED_DATE,
        "event_time": FIXED_TIME,
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
        location=event["location"]
    )

# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")
    tickets = int(data.get("tickets", 0))

    # ===== Google Sheets =====
    try:
        requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json={
                "timestamp": datetime.now().isoformat(),
                "event_id": event_id,
                "family_id": family_id,
                "status": status,
                "tickets": tickets,
                "ip": request.remote_addr
            },
            timeout=10
        )
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

    <CUST_DETAILS></CUST_DETAILS>

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

    requests.post(
        ZEBRA_UPDATE_URL,
        data=zebra_xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=15
    )

    return jsonify({"success": True})

# ======================
# THANKS PAGE
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
