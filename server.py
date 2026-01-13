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
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


def zebra_post(xml_body: str) -> str:
    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=15
    )
    return r.text


def parse_ddmmyyyy(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except:
        return None


def get_family_events(family_id):
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
                <EVE_HOUR></EVE_HOUR>
                <EVE_LOC></EVE_LOC>
            </FIELDS>
            <CON_FIELDS>
                <TOT_FFAM></TOT_FFAM>
                <PROV></PROV>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    text = zebra_post(xml_body)
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

            event_id = el.findtext("ID", "").strip()
            event_name = el.findtext(".//FIELDS/EV_N", "").strip()
            event_date = el.findtext(".//FIELDS/EV_D", "").strip()
            event_time = el.findtext(".//FIELDS/EVE_HOUR", "").strip()
            location = el.findtext(".//FIELDS/EVE_LOC", "").strip()
            tickets = int(el.findtext(".//CON_FIELDS/TOT_FFAM", "0"))
            prov = el.findtext(".//CON_FIELDS/PROV", "").strip()

            events.append({
                "event_id": event_id,
                "event_name": event_name,
                "event_date": event_date,
                "event_time": event_time,
                "location": location,
                "tickets": tickets,
                "prov": prov
            })

    return {
        "family_id": family_id,
        "family_name": family_name,
        "events": events
    }


def filter_events(events):
    today = datetime.today().date()
    valid = []

    for ev in events:
        if ev["prov"] != "1":
            continue

        d = parse_ddmmyyyy(ev["event_date"])
        if not d:
            continue

        if d < today:
            continue

        valid.append(ev)

    return valid


# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")
    event_id = request.args.get("event_id")

    if not family_id:
        return "Missing family_id", 400

    fam = get_family_events(family_id)
    if not fam:
        return "Family not found in Zebra"

    family_name = fam["family_name"]
    valid_events = filter_events(fam["events"])

    # אם אין event_id – מסך בחירת אירוע
    if not event_id:
        if len(valid_events) == 0:
            return "אין אירועים זמינים למשפחה זו"

        if len(valid_events) == 1:
            ev = valid_events[0]
        else:
            return render_template(
                "select_event.html",
                family_id=family_id,
                family_name=family_name,
                events=valid_events
            )
    else:
        ev = next((e for e in valid_events if e["event_id"] == event_id), None)
        if not ev:
            return "האירוע לא נמצא או לא מאושר"

    return render_template(
        "confirm.html",
        family_id=family_id,
        family_name=family_name,
        event_id=ev["event_id"],
        event_name=ev["event_name"],
        event_date=ev["event_date"],
        event_time=ev["event_time"],
        location=ev["location"],
        tickets=ev["tickets"]
    )


# ======================
# SUBMIT – זמני, רק בדיקה
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}
    print("SUBMIT RECEIVED:", data)
    return jsonify({"success": True})


# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")
    return f"""
    תודה!<br>
    סטטוס: {status}<br>
    כמות: {qty}
    """


@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
