from flask import Flask, render_template, request
import requests
from xml.etree import ElementTree as ET

app = Flask(__name__)

# ----------------------------------------
# הגדרות API לזברה
# ----------------------------------------
ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


# ----------------------------------------
# שליפת נתוני אירוע + משפחות (ASKEV)
# ----------------------------------------
def get_event_data(event_id):

    xml_request = f"""
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
                    <CELL></CELL>
                    <P_N></P_N>
                    <F_N></F_N>
                    <REA></REA>
                </FIELDS>

                <CON_FIELDS>
                    <TOT_FFAM></TOT_FFAM>
                    <ARRI></ARRI>
                    <TOT></TOT>
                    <PROV></PROV>
                </CON_FIELDS>

                <CON_FILTERS>
                    <PROV>1</PROV>
                </CON_FILTERS>
            </CONNECTION_CARD>
        </CONNECTION_CARDS>
    </ROOT>
    """

    response = requests.post(ZEBRA_URL, data=xml_request.encode("utf-8"))
    xml = ET.fromstring(response.text)

    fields = xml.find(".//CARD/FIELDS")

    event_info = {
        "event_name": fields.findtext("EV_N", ""),
        "event_date": fields.findtext("EV_D", ""),
        "event_time": fields.findtext("EVE_HOUR", ""),
        "event_location": fields.findtext("EVE_LOC", "")
    }

    families = []

    for con in xml.findall(".//CONNECTION_CARD"):
        fam = {
            "id": con.findtext(".//FIELDS/ID"),
            "family_name": con.findtext(".//FIELDS/CO_NAME"),
            "cell": con.findtext(".//FIELDS/CELL"),
            "tickets_approved": con.findtext(".//CON_FIELDS/TOT_FFAM"),
            "prov": con.findtext(".//CON_FIELDS/PROV")
        }
        families.append(fam)

    event_info["families"] = families

    return event_info


# ----------------------------------------
# דף הבית
# ----------------------------------------
@app.route("/")
def home():
    return """
    <script>
        window.location.href = "/confirm";
    </script>
    """


# ----------------------------------------
# דף אישור הגעה דינמי
# ----------------------------------------
@app.route("/confirm")
def confirm():

    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "חסר event_id או family_id בקישור", 400

    event = get_event_data(event_id)

    fam = next((f for f in event["families"] if f["id"] == family_id), None)

    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id}", 404

    family_name = fam["family_name"]
    tickets = int(fam["tickets_approved"]) if fam["tickets_approved"] else 0
    event_name = event["event_name"]
    event_date = event["event_date"]
    event_time = event["event_time"]
    location = event["event_location"]

    return render_template(
        "confirm.html",
        family_name=family_name,
        tickets=tickets,
        event_name=event_name,
        event_date=event_date,
        event_time=event_time,
        location=location
    )


# ----------------------------------------
# דף תודה
# ----------------------------------------
@app.route("/thanks")
def thanks():
    status = request.args.get("s")
    qty = request.args.get("q")
    return render_template("thanks.html", status=status, qty=qty)


# ----------------------------------------
# הפעלת השרת
# ----------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
