# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# HELPERS
# ======================
def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except Exception:
        return None

def extract_cards_safe(xml_text):
    cards = []
    for match in re.finditer(r"<CARD>(.*?)</CARD>", xml_text, re.DOTALL):
        try:
            card_xml = "<CARD>" + match.group(1) + "</CARD>"
            card_xml = card_xml.replace("&", "&amp;")
            cards.append(ET.fromstring(card_xml))
        except Exception:
            continue
    return cards

# ======================
# שליפת אירועים למשפחה – אישורי הגעה בלבד
# ======================
def get_family_events_for_confirm(family_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

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

    raw_xml = res.text

    try:
        tree = ET.fromstring(raw_xml)
        cards = tree.findall(".//CARD")
    except Exception:
        cards = extract_cards_safe(raw_xml)

    events = []

    for card in cards:
        for conn in card.findall(".//CARD_CONNECTION_*"):
            prov = (conn.findtext(".//CON_FIELDS/PROV") or "").strip()
            if prov != "1":
                continue

            ev_date = (conn.findtext(".//FIELDS/EV_D") or "").strip()
            parsed_date = parse_date(ev_date)
            if not parsed_date or parsed_date < datetime.today().date():
                continue

            events.append({
                "event_id": (conn.findtext("ID") or "").strip(),
                "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
                "event_date": ev_date,
                "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
                "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip()
            })

    events.sort(key=lambda e: parse_date(e["event_date"]))
    return events

# ======================
# SELECT EVENT – שלב ראשון
# ======================
@app.route("/select-event")
def select_event():
    family_id = request.args.get("family_id", "").strip()
    if not family_id:
        return "Missing family_id", 400

    events = get_family_events_for_confirm(family_id)

    return render_template(
        "select_event.html",
        family_id=family_id,
        family_name="",
        events=events
    )

# ======================
# CONFIRM – אישורי הגעה
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()

    if not family_id:
        return "Missing family_id", 400

    # אם אין event_id → שלב בחירת אירוע
    if not event_id:
        return redirect(url_for("select_event", family_id=family_id))

    return render_template(
        "confirm.html",
        family_id=family_id,
        event_id=event_id
    )

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "HOME OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
