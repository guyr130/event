# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# GOOGLE APPS SCRIPT (LOG)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyYTuGyUg1YLJyclKj31X5r1Aa4rcqo0oMHcsoR2KQKv7KKAFSu65lf7B1o8UM771oy/exec"

# ======================
# ZEBRA – שליפת משפחה ואירועים (בדיקה בלבד)
# ======================
def get_family_events(family_id: str):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{family_id}</ID_FILTER>

    <FIELDS>
        <CO_NAME></CO_NAME>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

            <FIELDS>
                <ID></ID>
                <EV_N></EV_N>
                <EV_D></EV_D>
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

    text = r.text
    tree = ET.fromstring(text)

    card = tree.find(".//CARDS/CARD")
    if card is None:
        return None

    family_name = card.findtext(".//FIELDS/CO_NAME", "").strip()

    events = []
    connections = card.find(".//CONNECTIONS_CARDS")
    if connections is not None:
        for el in list(connections):
            if not el.tag.startswith("CARD_CONNECTION_"):
                continue

            event_id = (el.findtext("ID") or "").strip()
            event_name = (el.findtext(".//FIELDS/EV_N") or "").strip()
            event_date = (el.findtext(".//FIELDS/EV_D") or "").strip()
            prov = (el.findtext(".//CON_FIELDS/PROV") or "").strip()

            events.append({
                "event_id": event_id,
                "event_name": event_name,
                "event_date": event_date,
                "prov": prov
            })

    return {
        "family_id": family_id,
        "family_name": family_name,
        "events": events
    }

# ======================
# CONFIRM – שלב בדיקה של זברה בלבד
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")

    if not family_id:
        return "Missing family_id", 400

    fam = get_family_events(family_id)

    if not fam:
        return "Family not found in Zebra", 404

    return f"""
    Family found ✔️<br>
    Family ID: {fam['family_id']}<br>
    Family Name: {fam['family_name']}<br>
    Events count: {len(fam['events'])}<br>
    First event sample:<br>
    {fam['events'][0] if fam['events'] else 'No events'}
    """

# ======================
# SUBMIT – בדיקת לוג בלבד (עוד לא משתמשים)
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    print("=== SUBMIT RECEIVED ===")
    print(data)

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data,
            timeout=12
        )
        print("GOOGLE STATUS:", r.status_code)
        print("GOOGLE RESPONSE:", r.text)
    except Exception as e:
        print("Sheets error:", e)

    return jsonify({"success": True})

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "Server is alive"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
