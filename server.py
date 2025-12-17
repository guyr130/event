from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

# ===============================
# Zebra API
# ===============================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ===============================
# Google Sheets WebApp
# ===============================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyK2wobbQUnN8hQ2HwL9sauJ4Nv8N3JpsRCdGGlrAY4KmEPnq2CUZFBaC_GZXJ7I3HT/exec"


# =====================================================
# שליפת נתוני אירוע + משפחות מזברה
# =====================================================
def get_event_data(event_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

            <FIELDS>
                <ID></ID>
                <CO_NAME></CO_NAME>
            </FIELDS>

            <CON_FIELDS>
                <TOT_FFAM></TOT_FFAM>
                <PROV></PROV>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    headers = {"Content-Type": "application/xml"}
    r = requests.post(ZEBRA_GET_URL, data=xml_body.encode("utf-8"), headers=headers)

    print("===== RAW XML FROM ZEBRA =====")
    print(r.text)
    print("===== END RAW XML =====")

    tree = ET.fromstring(r.text)
    card = tree.find(".//CARD")
    if card is None:
        return None

    event = {
        "event_name": card.findtext(".//EV_N", ""),
        "event_date": card.findtext(".//EV_D", ""),
        "event_time": card.findtext(".//EVE_HOUR", ""),
        "location": card.findtext(".//EVE_LOC", ""),
        "families": []
    }

    for conn in card.findall(".//CONNECTIONS_CARDS/*"):
        fam_id = conn.findtext("ID")
        name = conn.findtext(".//CO_NAME")
        tickets = conn.findtext(".//TOT_FFAM", "0")

        event["families"].append({
            "id": fam_id,
            "family_name": name,
            "tickets": int(tickets)
        })

    return event


# =====================================================
# עדכון אישור הגעה בזברה – זה החלק הקריטי
# =====================================================
def update_zebra_attendance(family_id, event_id, status, qty):
    status_text = "אישרו" if status == "yes" else "ביטלו"
    today = datetime.now().strftime("%d/%m/%Y")

    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <!-- קריטי! -->
    <CARD_TYPE_FILTER>business_customer</CARD_TYPE_FILTER>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{status_text}</A_C>
            <A_D>{today}</A_D>
            <NO_ARIVE>{qty}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    print(">>> ABOUT TO UPDATE ZEBRA <<<")
    print(xml_body)

    headers = {"Content-Type": "application/xml; charset=utf-8"}
    r = requests.post(
        ZEBRA_UPDATE_URL,
        data=xml_body.encode("utf-8"),
        headers=headers,
        timeout=15
    )

    print("[ZEBRA RESPONSE]")
    print(r.text)

    return r.text


# =====================================================
# דף אישור הגעה
# =====================================================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    event = get_event_data(event_id)
    if not event:
        return "שגיאה בשליפת האירוע", 500

    fam = next((f for f in event["families"] if f["id"] == family_id), None)
    if not fam:
        return "משפחה לא נמצאה באירוע", 404

    return render_template(
        "confirm.html",
        family_name=fam["family_name"],
        tickets=fam["tickets"],
        event_name=event["event_name"],
        event_date=event["event_date"],
        location=event["location"],
        event_id=event_id,
        zebra_family_id=family_id
    )


# =====================================================
# קבלת בחירת המשתמש
# =====================================================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")
    qty = int(data.get("tickets", 0))

    payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": qty,
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }

    # Google Sheets
    requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=10)

    # Zebra update
    update_zebra_attendance(
        family_id=family_id,
        event_id=event_id,
        status=status,
        qty=qty
    )

    return jsonify({"success": True})


# =====================================================
# עמוד תודה
# =====================================================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )


# =====================================================
# Health check
# =====================================================
@app.route("/")
def home():
    return "OK – server is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
