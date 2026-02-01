# -*- coding: utf-8 -*-
from flask import Flask, request, render_template
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
# HELPERS
# ======================
def parse_date_safe(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except Exception:
        return None

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

    <FIELDS>
        <FIELD>F_NAME</FIELD>
    </FIELDS>

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

    tree = ET.fromstring(res.text)
    today = datetime.today().date()
    events = []

    for container in tree.findall(".//CONNECTIONS_CARDS"):
        for conn in container:
            if not conn.tag.startswith("CARD_CONNECTION_"):
                continue

            prov = (conn.findtext(".//CON_FIELDS/PROV") or "").strip()
            date_raw = (conn.findtext(".//FIELDS/EV_D") or "").strip()
            date_obj = parse_date_safe(date_raw)

            if prov != "1":
                continue
            if not date_obj or date_obj < today:
                continue

            events.append({
                "event_id": conn.findtext("ID"),
                "event_name": conn.findtext(".//FIELDS/EV_N"),
                "event_date": date_raw,
                "event_time": conn.findtext(".//FIELDS/EVE_HOUR"),
                "location": conn.findtext(".//FIELDS/EVE_LOC"),
            })

    return events

# ======================
# ROUTES
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()

    if not family_id:
        return "Missing family_id", 400

    events = get_family_events(family_id)

    # 🔴 תיקון קריטי – אין אירועים אחרי סינון
    if not events:
        return render_template(
            "select_event.html",
            family_id=family_id,
            events=[],
            message="כרגע אין אירועים מאושרים ועתידיים לאישור הגעה"
        )

    # תמיד הצגת רשימה
    if not event_id:
        return render_template(
            "select_event.html",
            family_id=family_id,
            events=events
        )

    chosen = next((e for e in events if e["event_id"] == event_id), None)
    if not chosen:
        return "האירוע לא נמצא", 404

    return render_template(
        "confirm.html",
        family_id=family_id,
        event_id=chosen["event_id"],
        event_name=chosen["event_name"],
        event_date=chosen["event_date"],
        event_time=chosen["event_time"],
        location=chosen["location"]
    )

@app.route("/")
def home():
    return "SERVER OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
