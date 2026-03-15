# -*- coding: utf-8 -*-
from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET
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
def extract_cards_safe(xml_text):
    cards = []
    for match in re.finditer(r"<CARD_CONNECTION_.*?>.*?</CARD_CONNECTION_.*?>", xml_text, re.DOTALL):
        try:
            card_xml = match.group(0).replace("&", "&amp;")
            cards.append(ET.fromstring(card_xml))
        except Exception:
            continue
    return cards


# ======================
# שליפת אירוע בודד לפי event_id
# זה מסלול שהוכח בפוסטמן שעובד
# ======================
def get_event_by_id(event_id):
    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>EVEFAM</CARD_TYPE_FILTER>
    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
    </FIELDS>

    <ID></ID>
    <CARD_TYPE></CARD_TYPE>
</ROOT>
""".strip()

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA EVENT REQUEST FAILED:", e)
        return None

    print("==== RAW SINGLE EVENT XML ====")
    print(raw_xml)
    print("==== END SINGLE EVENT XML ====")

    try:
        tree = ET.fromstring(raw_xml)
        card = tree.find(".//CARD")
        if card is None:
            return None

        return {
            "event_id": (card.findtext("ID") or "").strip(),
            "event_name": (card.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (card.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (card.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (card.findtext(".//FIELDS/EVE_LOC") or "").strip()
        }
    except Exception as e:
        print("SINGLE EVENT PARSE FAILED:", e)
        return None


# ======================
# שליפת אירועים למשפחה – מסלול ישן דרך ASKEV
# ייתכן שעבד אצלך בעבר
# ======================
def get_family_events_for_confirm(family_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <ID_FILTER>
        <ID>{family_id}</ID>
    </ID_FILTER>

    <CONNECTION_CARD_DETAILS>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <FIELDS>
            <ID></ID>
            <EV_N></EV_N>
            <EV_D></EV_D>
            <EVE_HOUR></EVE_HOUR>
            <EVE_LOC></EVE_LOC>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
""".strip()

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA FAMILY EVENTS REQUEST FAILED:", e)
        return []

    print("==== RAW FAMILY EVENTS XML ====")
    print(raw_xml)
    print("==== END FAMILY EVENTS XML ====")

    try:
        tree = ET.fromstring(raw_xml)
        connections = [el for el in tree.iter() if el.tag.startswith("CARD_CONNECTION_")]
    except Exception:
        connections = extract_cards_safe(raw_xml)

    events = []
    for conn in connections:
        events.append({
            "event_id": (conn.findtext("ID") or "").strip(),
            "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (conn.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip()
        })

    # סינון תוצאות ריקות
    events = [e for e in events if e["event_id"] or e["event_name"]]
    return events


# ======================
# HOME
# ======================
@app.route("/")
def home():
    return "HOME OK"


# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()

    if not family_id:
        return "Missing family_id", 400

    # מסלול עדיף: אם יש event_id בלינק – שולפים ישירות אירוע בודד
    if event_id:
        ev = get_event_by_id(event_id)

        if not ev:
            return render_template(
                "confirm.html",
                family_id=family_id,
                event_id="",
                event_name="",
                event_date="",
                event_time="",
                location="",
                has_events=False
            )

        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id=ev["event_id"],
            event_name=ev["event_name"],
            event_date=ev["event_date"],
            event_time=ev["event_time"],
            location=ev["location"],
            has_events=True
        )

    # מסלול ישן: מנסים להביא את כל האירועים דרך ASKEV
    events = get_family_events_for_confirm(family_id)

    if not events:
        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id="",
            event_name="",
            event_date="",
            event_time="",
            location="",
            has_events=False
        )

    if len(events) == 1:
        ev = events[0]
        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id=ev["event_id"],
            event_name=ev["event_name"],
            event_date=ev["event_date"],
            event_time=ev["event_time"],
            location=ev["location"],
            has_events=True
        )

    return render_template(
        "select_event.html",
        family_id=family_id,
        family_name="",
        events=events
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
