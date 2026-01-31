# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

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
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxYOTETwFoJXbFHxNUwh3-AbwUsdnQ680194wn8svCFHE7c9zFreRI9hQhcDrPsAqM1/exec"

# ======================
# IDEMPOTENCY (ANTI DOUBLE-CLICK)
# ======================
recent_requests = {}
IDEMPOTENCY_WINDOW = 15  # seconds


def is_duplicate(event_id, family_id, status, tickets):
    now = time.time()
    key = f"{event_id}|{family_id}|{status}|{tickets}"

    expired = [k for k, v in recent_requests.items() if now - v > IDEMPOTENCY_WINDOW]
    for k in expired:
        del recent_requests[k]

    if key in recent_requests:
        return True

    recent_requests[key] = now
    return False


def zebra_post(xml_body: str, timeout: int = 15) -> str:
    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=timeout
    )
    return r.text


def parse_ddmmyyyy(date_str: str):
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except Exception:
        return None


# =========================================================
# NEW: EVENTS LIST (שליפת אירועים פעילים בלבד)
# =========================================================
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

    response = zebra_post(xml_body)
    tree = ET.fromstring(response)

    cards = tree.findall(".//CARD")
    result = []

    for card in cards:
        fields = card.find("FIELDS")
        if fields is None:
            continue

        if fields.findtext("STA_EV", "").strip() != "1":
            continue

        event = {
            "event_id": card.findtext("ID", "").strip(),
            "event_name": fields.findtext("EV_N", "").strip(),
            "event_date": fields.findtext("EV_D", "").strip(),
            "event_time": fields.findtext("EVE_HOUR", "").strip(),
            "location": fields.findtext("EVE_LOC", "").strip(),
            "order": int(fields.findtext("EVE_ORDER", "9999"))
        }

        result.append(event)

    def sort_key(e):
        d = parse_ddmmyyyy(e["event_date"]) or datetime.max.date()
        return (e["order"], d)

    result.sort(key=sort_key)
    return jsonify(result)


# ======================
# FAMILY EVENTS (אישורי הגעה – קיים)
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

    family_name = (card.findtext(".//FIELDS/CO_NAME") or "").strip()

    events = []
    connections = card.find(".//CONNECTIONS_CARDS")
    if connections is not None:
        for el in list(connections):
            if not el.tag.startswith("CARD_CONNECTION_"):
                continue

            event_id = (el.findtext("ID") or "").strip()
            event_name = (el.findtext(".//FIELDS/EV_N") or "").strip()
            event_date = (el.findtext(".//FIELDS/EV_D") or "").strip()
            event_time = (el.findtext(".//FIELDS/EVE_HOUR") or "").strip()
            location = (el.findtext(".//FIELDS/EVE_LOC") or "").strip()

            tickets_raw = (el.findtext(".//CON_FIELDS/TOT_FFAM") or "0").strip()
            try:
                tickets = int(tickets_raw) if tickets_raw else 0
            except Exception:
                tickets = 0

            prov = (el.findtext(".//CON_FIELDS/PROV") or "").strip()

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
        if str(ev.get("prov", "")).strip() != "1":
            continue

        d = parse_ddmmyyyy(ev.get("event_date", ""))
        if not d or d < today:
            continue

        valid.append(ev)

    valid.sort(key=lambda x: (
        parse_ddmmyyyy(x.get("event_date", "")) or today,
        x.get("event_time", "00:00")
    ))

    return valid


# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = (request.args.get("family_id") or "").strip()
    event_id = (request.args.get("event_id") or "").strip()

    if not family_id:
        return "Missing family_id", 400

    fam = get_family_events(family_id)
    if not fam:
        return "Family not found in Zebra", 404

    family_name = fam["family_name"]
    valid_events = filter_events(fam["events"])

    if not event_id:
        if len(valid_events) == 0:
            return "אין אירועים זמינים למשפחה זו", 404

        if len(valid_events) == 1:
            ev = valid_events[0]
            return render_template("confirm.html", family_id=family_id, family_name=family_name, **ev)

        return render_template("select_event.html", family_id=family_id, family_name=family_name, events=valid_events)

    chosen = next((e for e in valid_events if e["event_id"] == event_id), None)
    if not chosen:
        return "האירוע לא נמצא / לא מאושר / תאריך עבר", 404

    return render_template("confirm.html", family_id=family_id, family_name=family_name, **chosen)


# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}

    event_id = str(data.get("event_id") or "").strip()
    family_id = str(data.get("family_id") or "").strip()
    status = str(data.get("status") or "").strip()
    tickets = int(data.get("tickets", 0) or 0)

    family_name = str(data.get("family_name") or "").strip()
    event_name = str(data.get("event_name") or "").strip()

    if not event_id or not family_id or status not in ("yes", "no"):
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    if is_duplicate(event_id, family_id, status, tickets):
        return jsonify({"success": True, "duplicate": True})

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    status_he = "אישרו" if status == "yes" else "ביטלו"
    if status == "no":
        tickets = 0

    payload = {
        "timestamp": timestamp,
        "family_id": family_id,
        "family_name": family_name,
        "event_id": event_id,
        "event_name": event_name,
        "status": status_he,
        "tickets": tickets
    }

    try:
        r = requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=20)
        return jsonify({"success": True, "google_status": r.status_code})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ======================
# THANKS + HEALTH
# ======================
@app.route("/thanks")
def thanks():
    return render_template("thanks.html")


@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
