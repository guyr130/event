from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

# === Zebra API (GET – קיים, לא נוגעים) ===
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"

# === Zebra API (UPDATE – חדש) ===
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "17/12/2025"

# === Google Sheets Web App ===
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyK2wobbQUnN8hQ2HwL9sauJ4Nv8N3JpsRCdGGlrAY4KmEPnq2CUZFBaC_GZXJ7I3HT/exec"


# =========================
# שליפת אירוע (כמו שהיה)
# =========================
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
    response = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers=headers
    )

    raw = response.text.strip()
    if raw == "" or "function not found" in raw.lower():
        return None

    tree = ET.fromstring(raw)
    card = tree.find(".//CARD")
    if card is None:
        return None

    event_data = {
        "event_name": card.findtext(".//EV_N", default=""),
        "event_date": card.findtext(".//EV_D", default=""),
        "event_time": card.findtext(".//EVE_HOUR", default=""),
        "event_location": card.findtext(".//EVE_LOC", default=""),
        "families": []
    }

    connections = card.find("CONNECTIONS_CARDS")
    if connections is not None:
        for element in connections:
            if element.tag.startswith("CARD_CONNECTION_"):
                event_data["families"].append({
                    "id": element.findtext("ID"),
                    "family_name": element.findtext(".//CO_NAME"),
                    "tickets_approved": element.findtext(".//TOT_FFAM"),
                    "approved": element.findtext(".//PROV")
                })

    return event_data


# =========================
# דף אישור הגעה (כמו שהיה)
# =========================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing event_id or family_id", 400

    event = get_event_data(event_id)
    if event is None:
        return "שגיאה בשליפת האירוע", 404

    fam = next((f for f in event["families"] if f["id"] == family_id), None)
    if fam is None:
        return "משפחה לא נמצאה באירוע", 404

    return render_template(
        "confirm.html",
        family_name=fam["family_name"],
        tickets=int(fam["tickets_approved"]),
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["event_location"]
    )


# =========================
# SUBMIT – כאן רק הוספנו Zebra
# =========================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": data.get("event_id"),
        "family_id": data.get("family_id"),
        "status": data.get("status"),
        "tickets": data.get("tickets"),
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }

    # ---------- Google Sheets (לא נוגעים) ----------
    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=10
        )
        print("Sheets:", r.status_code)
    except Exception as e:
        print("Sheets error:", e)

    # ---------- Zebra UPDATE (תוספת בלבד) ----------
    zebra_status = "אישרו" if payload["status"] == "yes" else "ביטלו"
    zebra_tickets = payload["tickets"] if payload["status"] == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{payload["family_id"]}</ID>
    </IDENTIFIER>

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{payload["event_id"]}</VALUE>

        <FIELDS>
            <A_C>{zebra_status}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        zr = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=10
        )
        print("Zebra response:", zr.text[:300])
    except Exception as e:
        print("Zebra error:", e)

    return jsonify({"success": True})


# =========================
# תודה
# =========================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )


# =========================
# Health
# =========================
@app.route("/")
def home():
    return "OK – server is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
