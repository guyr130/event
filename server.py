from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

# ========================
# Zebra credentials
# ========================
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php"

# ========================
# Google Sheets WebApp
# ========================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyK2wobbQUnN8hQ2HwL9sauJ4Nv8N3JpsRCdGGlrAY4KmEPnq2CUZFBaC_GZXJ7I3HT/exec"


# ========================
# Fetch event + ASKEV
# ========================
def get_event_data(event_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N/>
        <EV_D/>
        <EVE_HOUR/>
        <EVE_LOC/>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
            <FIELDS>
                <ID/>
                <CO_NAME/>
            </FIELDS>
            <CON_FIELDS>
                <TOT_FFAM/>
                <PROV/>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=20
    )

    print("\n===== RAW XML FROM ZEBRA =====")
    print(r.text)
    print("===== END RAW XML =====\n")

    tree = ET.fromstring(r.text)
    card = tree.find(".//CARD")
    if card is None:
        return None

    event = {
        "event_name": card.findtext(".//EV_N", ""),
        "event_date": card.findtext(".//EV_D", ""),
        "event_time": card.findtext(".//EVE_HOUR", ""),
        "event_location": card.findtext(".//EVE_LOC", ""),
        "families": []
    }

    connections = card.find("CONNECTIONS_CARDS")
    for conn in connections:
        if conn.tag.startswith("CARD_CONNECTION_"):
            event["families"].append({
                "id": conn.findtext("ID"),
                "family_name": conn.findtext(".//CO_NAME"),
                "tickets": conn.findtext(".//TOT_FFAM", "0"),
                "prov": conn.findtext(".//PROV", "0")
            })

    return event


# ========================
# Update ASKEV (THE FIX)
# ========================
def update_askev(family_id, event_id, status, tickets):
    today = datetime.now().strftime("%d/%m/%Y")
    status_text = "אישרו" if status == "yes" else "ביטלו"
    qty = tickets if status == "yes" else 0

    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

        <!-- IMPORTANT -->
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <CON_FIELDS>
            <A_C>{status_text}</A_C>
            <A_D>{today}</A_D>
            <NO_ARIVE>{qty}</NO_ARIVE>
        </CON_FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
""".strip()

    print("\n>>> UPDATE ASKEV <<<")
    print(xml_body)

    r = requests.post(
        ZEBRA_UPDATE_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=20
    )

    print("[ZEBRA RESPONSE]")
    print(r.text)

    return "code>0" in r.text or "SUCCESS" in r.text


# ========================
# Confirm page
# ========================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    event = get_event_data(event_id)
    if not event:
        return "Event not found", 404

    fam = next((f for f in event["families"] if f["id"] == family_id), None)
    if not fam:
        return "Family not found", 404

    return render_template(
        "confirm.html",
        family_name=fam["family_name"],
        tickets=int(fam["tickets"]),
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["event_location"],
        event_id=event_id,
        zebra_family_id=family_id
    )


# ========================
# Submit
# ========================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    event_id = data["event_id"]
    family_id = data["family_id"]
    status = data["status"]
    tickets = int(data["tickets"])

    # ---- Google Sheets
    payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": tickets,
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent", "")
    }

    requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=10)

    # ---- Zebra ASKEV
    update_askev(family_id, event_id, status, tickets)

    return jsonify({"success": True})


# ========================
# Thanks
# ========================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )


# ========================
# Health check
# ========================
@app.route("/")
def home():
    return "OK – server running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
