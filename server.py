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
def clean_xml(text: str) -> str:
    """
    מנקה תווים לא חוקיים ל-XML (בעיה מוכרת בזברה)
    """
    if not text:
        return ""
    # הסרת תווי בקרה לא חוקיים
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    return text


def parse_date(d):
    try:
        return datetime.strptime(d, "%d/%m/%Y").date()
    except Exception:
        return None


# ======================
# EVENTS – רשימת אירועים
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

    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=20
    )

    # 🔴 ניקוי XML לפני parsing
    clean_response = clean_xml(r.text)

    tree = ET.fromstring(clean_response)

    events = []

    for card in tree.findall(".//CARD"):
        f = card.find("FIELDS")
        if f is None:
            continue

        if (f.findtext("STA_EV") or "").strip() != "1":
            continue

        ev_date = (f.findtext("EV_D") or "").strip()
        parsed_date = parse_date(ev_date)
        if not parsed_date:
            continue

        events.append({
            "id": card.findtext("ID"),
            "name": (f.findtext("EV_N") or "").strip(),
            "date": ev_date,
            "time": (f.findtext("EVE_HOUR") or "").strip(),
            "location": (f.findtext("EVE_LOC") or "").strip(),
            "order": int((f.findtext("EVE_ORDER") or "999").strip() or 999)
        })

    # מיון: קודם סדר הצגה, ואז תאריך
    events.sort(key=lambda e: (e["order"], parse_date(e["date"])))

    return jsonify(events)


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
