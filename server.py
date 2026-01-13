# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import time

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "20/12/2025"
FIXED_TIME = "08:00"

# ======================
# GOOGLE APPS SCRIPT (LOG)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyYTuGyUg1YLJyclKj31X5r1Aa4rcqo0oMHcsoR2KQKv7KKAFSu65lf7B1o8UM771oy/exec"

# ======================
# MEMORY FOR IDEMPOTENCY
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


def parse_ddmmyyyy(date_str: str):
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except Exception:
        return None


def zebra_post(xml_body: str, timeout: int = 15) -> str:
    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=timeout
    )
    return r.text


# ======================
# GET FAMILY + EVENTS (ZEBRA)  ✅ חדש
# ======================
def get_family_events(family_id: str):
    """
    מחזיר:
    {
      "family_id": "...",
      "family_name": "...",
      "events": [
        {
          "event_id": "...",
          "event_name": "...",
          "event_date": "DD/MM/YYYY",
          "event_time": "HH:MM",
          "location": "...",
          "tickets_approved": int,
          "prov": "0/1"
        }, ...
      ]
    }
    """
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

            event_id = (el.findtext("ID") or "").strip()
            event_name = (el.findtext(".//FIELDS/EV_N") or "").strip()
            event_date = (el.findtext(".//FIELDS/EV_D") or "").strip()
            event_time = (el.findtext(".//FIELDS/EVE_HOUR") or "").strip() or FIXED_TIME
            location = (el.findtext(".//FIELDS/EVE_LOC") or "").strip()
            tickets_approved = int((el.findtext(".//CON_FIELDS/TOT_FFAM") or "0").strip() or "0")
            prov = (el.findtext(".//CON_FIELDS/PROV") or "0").strip()

            events.append({
                "event_id": event_id,
                "event_name": event_name,
                "event_date": event_date,
                "event_time": event_time,
                "location": location,
                "tickets_approved": tickets_approved,
                "prov": prov
            })

    return {
        "family_id": family_id,
        "family_name": family_name,
        "events": events
    }


def filter_events(events):
    """
    מציגים רק:
    - PROV == "1"
    - תאריך מהיום והלאה
    """
    today = datetime.today().date()
    out = []
    for ev in events:
        if str(ev.get("prov", "")).strip() != "1":
            continue

        ev_date = parse_ddmmyyyy(ev.get("event_date", ""))
        if ev_date is None:
            # אם אין תאריך תקין – לא מציגים (יותר בטוח)
            continue

        if ev_date < today:
            continue

        out.append(ev)

    # מיון לפי תאריך ואז שעה
    def sort_key(x):
        d = parse_ddmmyyyy(x.get("event_date", "")) or today
        t = (x.get("event_time", "") or "00:00").strip()
        return (d, t)

    out.sort(key=sort_key)
    return out


# ======================
# CONFIRM PAGE  ✅ תומך גם בלינק אחוד וגם בלינק ישן
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id")
    event_id = request.args.get("event_id")

    if not family_id:
        return "Missing family_id", 400

    fam = get_family_events(family_id)
    if not fam:
        return "Family not found in Zebra", 404

    family_name = fam["family_name"]
    valid_events = filter_events(fam["events"])

    # אם אין event_id => מצב לינק אחוד: מציגים רשימת אירועים / או קופצים ל-1
    if not event_id:
        if len(valid_events) == 0:
            return "No approved future events for this family", 404

        if len(valid_events) == 1:
            ev = valid_events[0]
            return render_template(
                "confirm.html",
                event_id=ev["event_id"],
                family_id=family_id,
                family_name=family_name,
                tickets=ev["tickets_approved"],
                event_name=ev["event_name"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                location=ev["location"]
            )

        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name=family_name,
            events=valid_events
        )

    # אם יש event_id (לינק ישן או בחירה מהמסך)
    chosen = next((e for e in valid_events if e["event_id"] == str(event_id).strip()), None)
    if not chosen:
        return "Event not allowed (not approved / past / not connected)", 404

    return render_template(
        "confirm.html",
        event_id=chosen["event_id"],
        family_id=family_id,
        family_name=family_name,
        tickets=chosen["tickets_approved"],
        event_name=chosen["event_name"],
        event_date=chosen["event_date"],
        event_time=chosen["event_time"],
        location=chosen["location"]
    )


# ======================
# SUBMIT  ✅ כותב LOG + משאיר Zebra UPDATE כמו היום
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = str(data.get("event_id") or "").strip()
    family_id = str(data.get("family_id") or "").strip()
    status = str(data.get("status") or "").strip()  # yes/no
    tickets = int(data.get("tickets", 0) or 0)

    # אופציונלי (נשלח מה-HTML)
    family_name = (data.get("family_name") or "").strip()
    event_name = (data.get("event_name") or "").strip()

    if not event_id or not family_id or status not in ("yes", "no"):
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    print("=== SUBMIT ===", event_id, family_id, status, tickets)

    # ===== IDEMPOTENCY CHECK =====
    if is_duplicate(event_id, family_id, status, tickets):
        print("⚠ DUPLICATE REQUEST IGNORED")
        return jsonify({"success": True, "duplicate": True})

    # אם אין שמות (ליתר ביטחון), נשלוף מהזברה
    if not family_name or not event_name:
        fam = get_family_events(family_id)
        if fam:
            family_name = family_name or fam.get("family_name", "")
            ev = next((e for e in fam.get("events", []) if str(e.get("event_id")) == event_id), None)
            if ev:
                event_name = event_name or ev.get("event_name", "")

    # ===== Google LOG =====
    status_he = "אישרו" if status == "yes" else "ביטלו"
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    sheets_payload = {
        "timestamp": timestamp,
        "family_id": family_id,
        "family_name": family_name,
        "event_id": event_id,
        "event_name": event_name,
        "status": status_he,
        "tickets": tickets
    }

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(sheets_payload, ensure_ascii=False),
            timeout=12
        )
        print("GOOGLE STATUS:", r.status_code, r.text[:200])
    except Exception as e:
        print("Sheets error:", e)

    # ===== Zebra UPDATE (נשאר כמו אצלך) =====
    a_c = "אישרו" if status == "yes" else "ביטלו"
    no_arive = tickets if status == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{a_c}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{no_arive}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        z = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15
        )
        print("ZEBRA STATUS:", z.status_code, z.text[:200])
    except Exception as e:
        print("Zebra error:", e)

    return jsonify({"success": True})


# ======================
# THANKS PAGE
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty", "0")
    event_id = request.args.get("event_id", "")
    family_id = request.args.get("family_id", "")
    return render_template("thanks.html", status=status, qty=qty, event_id=event_id, family_id=family_id)


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK – server is running"


# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
