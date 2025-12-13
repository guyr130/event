from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
USERNAME = "IVAPP"
PASSWORD = "1q2w3e4r"

def get_event_data(event_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{USERNAME}</USERNAME>
        <PASSWORD>{PASSWORD}</PASSWORD>
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

    print("===== RAW ZEBRA RESPONSE =====")
    print(response.text)
    print("===== END RESPONSE =====")

    tree = ET.fromstring(response.text)

    card = tree.find(".//CARD")
    if card is None:
        return None

    event_name = card.findtext(".//EV_N", default="")
    event_date = card.findtext(".//EV_D", default="")
    event_time = card.findtext(".//EVE_HOUR", default="")
    event_location = card.findtext(".//EVE_LOC", default="")

    families = []
    for fam in card.findall(".//CONNECTION_CARD"):
        fam_id = fam.findtext("ID", "")
        name = fam.findtext(".//CO_NAME", "")
        tickets = fam.findtext(".//TOT_FFAM", "0")
        approved = fam.findtext(".//PROV", "0")

        families.append({
            "id": fam_id,
            "name": name,
            "tickets": int(tickets),
            "approved": approved
        })

    return {
        "event_name": event_name,
        "event_date": event_date,
        "event_time": event_time,
        "event_location": event_location,
        "families": families
    }


@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "חסר event_id או family_id"

    data = get_event_data(event_id)
    if not data:
        return f"שגיאה: האירוע {event_id} לא נמצא"

    family = next((f for f in data["families"] if f["id"] == family_id), None)
    if not family:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id}"

    return render_template(
        "confirm.html",
        family_name=family["name"],
        tickets=family["tickets"],
        event_name=data["event_name"],
        event_date=data["event_date"],
        event_time=data["event_time"],
        location=data["event_location"]
    )


@app.route("/")
def home():
    return "OK – Server Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
