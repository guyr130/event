# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, redirect, url_for
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
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
    """
    חילוץ CARD_CONNECTION גם אם ה־XML הכללי שבור
    """
    cards = []
    for match in re.finditer(r"<CARD_CONNECTION_.*?>.*?</CARD_CONNECTION_.*?>", xml_text, re.DOTALL):
        try:
            card_xml = match.group(0).replace("&", "&amp;")
            cards.append(ET.fromstring(card_xml))
        except Exception:
            continue
    return cards


# ======================
# שליפת אירועים למשפחה – אישורי הגעה
# ======================
def get_family_events_for_confirm(family_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <FIELDS>
        <ID></ID>
    </FIELDS>

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
        connections = tree.findall(".//CARD_CONNECTION_*")
    except Exception:
        connections = extract_cards_safe(raw_xml)

    today = date.today()
    events = []

    for conn in connections:
        prov = (conn.findtext(".//CON_FIELDS/PROV") or "").strip()
        if prov != "1":
            continue

        ev_date_raw = (conn.findtext(".//FIELDS/EV_D") or "").strip()
        ev_date = parse_date(ev_date_raw)

        # סינון תאריך – היום והלאה
        if not ev_date or ev_date < today:
            continue

        events.append({
            "event_id": (conn.findtext("ID") or "").strip(),
            "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": ev_date_raw,
            "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip()
        })

    # מיון לפי תאריך
    events.sort(key=lambda e: parse_date(e["event_date"]))
    return events


# ======================
# CONFIRM – נקודת כניסה לאישורי הגעה
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()

    if not family_id:
        return "Missing family_id", 400

    events = get_family_events_for_confirm(family_id)

    if not events:
        return "אין אירועים זמינים לאישור הגעה", 404

    # אם לא נבחר אירוע
    if not event_id:
        if len(events) == 1:
            # אירוע אחד → מעבר ישיר לאישור
            ev = events[0]
            return render_template(
                "confirm.html",
                family_id=family_id,
                event_id=ev["event_id"],
                event_name=ev["event_name"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                location=ev["location"],
                tickets=0
            )

        # יותר מאירוע אחד → בחירת אירוע
        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name="",
            events=events
        )

    # יש event_id → מציגים אישור הגעה
    chosen = next((e for e in events if e["event_id"] == event_id), None)
    if not chosen:
        return "האירוע לא נמצא או לא זמין", 404

    return render_template(
        "confirm.html",
        family_id=family_id,
        event_id=chosen["event_id"],
        event_name=chosen["event_name"],
        event_date=chosen["event_date"],
        event_time=chosen["event_time"],
        location=chosen["location"],
        tickets=0
    )


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "HOME OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
