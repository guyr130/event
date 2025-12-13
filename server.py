from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# === Zebra API ===
ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


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
    response = requests.post(ZEBRA_URL, data=xml_body.encode("utf-8"), headers=headers)

    # לוג למעקב
    print("\n===== RAW XML FROM ZEBRA =====")
    print(response.text)
    print("===== END RAW XML =====\n")

    raw = response.text.strip()
    if raw == "" or "function not found" in raw.lower():
        return None

    tree = ET.fromstring(raw)
    card = tree.find(".//CARD")
    if card is None:
        return None

    # נתוני האירוע
    event_data = {
        "event_name": card.findtext(".//EV_N", default=""),
        "event_date": card.findtext(".//EV_D", default=""),
        "event_time": card.findtext(".//EVE_HOUR", default=""),
        "event_location": card.findtext(".//EVE_LOC", default=""),
        "families": []
    }

    # === שליפת המשפחות מתוך CONNECTIONS_CARDS ===
    connections = card.find("CONNECTIONS_CARDS")
    if connections is not None:
        for element in connections:
            if element.tag.startswith("CARD_CONNECTION_"):
                fam_id = element.findtext("ID")
                name = element.findtext(".//CO_NAME")
                tickets = element.findtext(".//TOT_FFAM")
                approved = element.findtext(".//PROV")

                event_data["families"].append({
                    "id": fam_id,
                    "family_name": name,
                    "tickets_approved": tickets,
                    "approved": approved
                })

    return event_data


@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing event_id or family_id", 400

    event = get_event_data(event_id)
    if event is None:
        return f"שגיאה בשליפת האירוע {event_id}", 404

    fam = next((f for f in event["families"] if f["id"] == family_id), None)
    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id}", 404

    return render_template(
        "confirm.html",
        family_name=fam["family_name"],
        tickets=int(fam["tickets_approved"]),
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["event_location"]
    )


@app.route("/thanks")
def thanks():
    msg = request.args.get("msg", "תודה רבה")
    return render_template("thanks.html", message=msg)


@app.route("/")
def home():
    return "OK – server is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
