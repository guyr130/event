# -*- coding: utf-8 -*-
from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET
import re

app = Flask(__name__)

ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# חילוץ CARD_CONNECTION_* בצורה בטוחה
# ======================
def extract_connections(xml_text):
    connections = []
    for match in re.finditer(r"<CARD_CONNECTION_.*?>.*?</CARD_CONNECTION_.*?>", xml_text, re.DOTALL):
        try:
            block = match.group(0).replace("&", "&amp;")
            connections.append(ET.fromstring(block))
        except Exception:
            continue
    return connections

# ======================
# שליפת אירועים למשפחה
# ======================
def get_family_events(family_id):
    xml_body = f"""
<ROOT>
  <PERMISSION>
    <USERNAME>{ZEBRA_USER}</USERNAME>
    <PASSWORD>{ZEBRA_PASS}</PASSWORD>
  </PERMISSION>

  <CARD_TYPE>business_customer</CARD_TYPE>
  <ID_FILTER>{family_id}</ID_FILTER>

  <CONNECTION_CARDS>
    <CONNECTION_CARD>
      <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
      <FIELDS>
        <ID></ID>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
      </FIELDS>
      <CON_FIELDS>
        <PROV></PROV>
      </CON_FIELDS>
    </CONNECTION_CARD>
  </CONNECTION_CARDS>
</ROOT>
""".strip()

    res = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=20
    )

    connections = extract_connections(res.text)

    events = []
    for conn in connections:
        prov = (conn.findtext(".//CON_FIELDS/PROV") or "").strip()
        if prov != "1":
            continue

        events.append({
            "event_id": (conn.findtext("ID") or "").strip(),
            "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (conn.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip(),
        })

    return events

# ======================
# ROUTES
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    if not family_id:
        return "Missing family_id", 400

    events = get_family_events(family_id)

    if not events:
        return render_template(
            "select_event.html",
            family_id=family_id,
            events=[],
            message="אין אירועים מאושרים לאישור הגעה"
        )

    return render_template(
        "select_event.html",
        family_id=family_id,
        events=events
    )

@app.route("/")
def home():
    return "SERVER OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
