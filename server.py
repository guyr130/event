from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# === IMPORT ZEBRA UPDATE ===
from zebra_api import update_zebra_attendance

app = Flask(__name__)

# === Zebra API (READ) ===
ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# === Google Sheets Web App ===
GOOGLE_SHEETS_WEBAPP_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbyK2wobbQUnN8hQ2HwL9sauJ4Nv8N3JpsRCdGGlrAY4KmEPnq2CUZFBaC_GZXJ7I3HT"
    "/exec"
)


# =========================
# שליפת נתוני אירוע מזברה
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
        ZEBRA_URL,
        data=xml_body.encode("utf-8"),
        headers=headers,
        timeout=20
    )

    print("\n===== RAW XML FROM ZEBRA =====")
    print(response.text)
    print("===== END RAW XML =====\n")

    raw = response.text.strip()
    if not raw or "function not found" in raw.lower():
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
# דף אישור הגעה
# =========================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing event_id or family_id", 400

    event = get_event_data(event_id)
    if not event:
        return f"שגיאה בשליפת האירוע {event_id}", 404

    fam = next(
        (f for f in event["families"] if f["id"] == family_id),
        None
    )

    if not fam:
        return f"לא נמצאה משפחה {family_id}", 404

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
# SUBMIT – Sheets + Zebra
# =========================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = int(data.get("event_id"))
    family_id = int(data.get("family_id"))
    status = data.get("status")  # yes / no
    tickets = int(data.get("tickets", 0))

    payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": tickets,
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
    }

    # ---- 1. Google Sheets ----
    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=10
        )
        print("===== SENT TO GOOGLE SHEETS =====")
        print(payload)
        print("Sheets response:", r.status_code, r.text[:200])
        print("================================\n")
    except Exception as e:
        print("ERROR sending to Google Sheets:", str(e))

    # ---- 2. Zebra Update ----
    print(">>> ABOUT TO UPDATE ZEBRA <<<")

    update_zebra_attendance(
        family_id=family_id,
        event_id=event_id,
        status=status,
        qty=tickets
    )

    return jsonify({"success": True})


# =========================
# עמוד תודה
# =========================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )


# =========================
# Health Check
# =========================
@app.route("/")
def home():
    return "OK – server is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
