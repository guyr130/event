# -*- coding: utf-8 -*-
from flask import Flask, jsonify
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
    """
    חילוץ <CARD> גם אם ה-XML הכללי שבור (בעיה ידועה בזברה)
    """
    cards = []
    for match in re.finditer(r"<CARD>(.*?)</CARD>", xml_text, re.DOTALL):
        try:
            card_xml = "<CARD>" + match.group(1) + "</CARD>"
            # תיקון קריטי: & לא חוקי
            card_xml = card_xml.replace("&", "&amp;")
            card = ET.fromstring(card_xml)
            cards.append(card)
        except Exception:
            continue
    return cards


# ======================
# EVENTS – API ציבורי
# ======================
@app.route("/events")
def events():
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>EVEFAM</CARD_TYPE_FILTER>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
        <EVE_ORDER></EVE_ORDER>
        <STA_EV></STA_EV>
    </FIELDS>
</ROOT>
""".strip()

    response = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=20
    )

    raw_xml = response.text

    # ניסיון parsing רגיל
    try:
        tree = ET.fromstring(raw_xml)
        cards = tree.findall(".//CARD")
    except Exception:
        # fallback ל-XML שבור
        cards = extract_cards_safe(raw_xml)

    result = []

    for card in cards:
        fields = card.find("FIELDS")
        if fields is None:
            continue

        # רק אירועים פעילים
        if (fields.findtext("STA_EV") or "").strip() != "1":
            continue

        ev_date = (fields.findtext("EV_D") or "").strip()
        parsed_date = parse_date(ev_date)
        if not parsed_date:
            continue

        result.append({
            "id": (card.findtext("ID") or "").strip(),
            "name": (fields.findtext("EV_N") or "").strip(),
            "date": ev_date,
            "time": (fields.findtext("EVE_HOUR") or "").strip(),
            "location": (fields.findtext("EVE_LOC") or "").strip(),
            "order": int((fields.findtext("EVE_ORDER") or "999") or 999)
        })

    # מיון: קודם סדר הצגה, ואז תאריך
    result.sort(key=lambda e: (e["order"], parse_date(e["date"])))

    return jsonify(result)


# ======================
# HEALTH CHECK
# ======================
@app.route("/")
def home():
    return "Server is alive"

from flask import render_template

from flask import render_template

@app.route("/events-page", strict_slashes=False)
def events_page():
    return render_template("events.html")
