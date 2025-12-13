from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php"
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
"""

    headers = {"Content-Type": "application/xml"}
    response = requests.post(ZEBRA_URL, data=xml_body.encode("utf-8"), headers=headers)

    # ניסיון פרסינג
    try:
        root = ET.fromstring(response.text)
    except:
        print("XML ERROR:", response.text)
        return None

    card = root.find(".//CARD")
    if card is None:
        return None

    # נתוני האירוע
    event_data = {
        "event_name": card.findtext("FIELDS/EV_N", ""),
        "event_date": card.findtext("FIELDS/EV_D", ""),
        "event_time": card.findtext("FIELDS/EVE_HOUR", ""),
        "event_location": card.findtext("FIELDS/EVE_LOC", ""),
        "families": []
    }

    # שליפת כל קשרי ASKEV לפי תגיות CARD_CONNECTION_XXXX
    for f in card.find("CONNECTIONS_CARDS").iter():
        if f.tag.startswith("CARD_CONNECTION_"):

            fam_id = f.findtext("ID", "")
            fam_name = f.findtext("FIELDS/CO_NAME", "")
            tickets = f.findtext("CON_FIELDS/TOT_FFAM", "0")
            approved = f.findtext("CON_FIELDS/PROV", "")

            event_data["families"].append({
                "id": fam_id,
                "family_name": fam_name,
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
        tickets=fam["tickets_approved"],
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["event_location"]
    )


@app.route("/")
def home():
    return "OK – server is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
