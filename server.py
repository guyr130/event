from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


# --------------------------------------------------------
# המרה של זמן UNIX לשעה תקינה
# --------------------------------------------------------
def format_time(ts):
    try:
        ts = int(ts)
        return datetime.fromtimestamp(ts).strftime("%H:%M")
    except:
        return ""


# --------------------------------------------------------
# שליפה מהזברה → אירוע + משפחות
# --------------------------------------------------------
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
                </FIELDS>

                <CON_FIELDS>
                    <TOT_FFAM></TOT_FFAM>
                    <PROV></PROV>
                </CON_FIELDS>
            </CONNECTION_CARD>
        </CONNECTION_CARDS>
    </ROOT>
    """

    response = requests.post(ZEBRA_URL, data=xml_request.encode("utf-8"))
    response_text = response.text.strip()

    # הדפסה ללוגים ל-Debug
    print("===== RAW XML FROM ZEBRA =====")
    print(response_text)
    print("===== END RAW XML =====")

    # פרסינג XML
    tree = ET.fromstring(response_text)

    card = tree.find(".//CARD")

    event_name = card.findtext(".//EV_N", "")
    event_date = card.findtext(".//EV_D", "")
    event_time_raw = card.findtext(".//EVE_HOUR", "")
    event_time = format_time(event_time_raw)
    event_location = card.findtext(".//EVE_LOC", "")

    # שליפת משפחות ASKEV
    families = []
    for fam in card.findall(".//CARD_CONNECTION_*/"):  # כל משפחה
        pass  # לא נעשה שימוש בניסוי הזה


    # שליפת משפחות בצורה נכונה:
    families = []
    for fam in card.findall(".//CARD_CONNECTION_*/.."):  # תיקון גישה
        fid = fam.findtext(".//ID")
        name = fam.findtext(".//CO_NAME")
        total = fam.findtext(".//TOT_FFAM")
        prov = fam.findtext(".//PROV")

        families.append({
            "id": fid,
            "family_name": name,
            "tickets_total": int(total) if total else 0,
            "tickets_approved": int(prov) if prov else 0
        })

    return {
        "event_name": event_name,
        "event_date": event_date,
        "event_time": event_time,
        "event_location": event_location,
        "families": families,
    }


# --------------------------------------------------------
# דף אישור הגעה
# --------------------------------------------------------
@app.route("/confirm")
def confirm():

    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "חסר event_id או family_id בקישור", 400

    event = get_event_data(event_id)

    # חיפוש משפחה
    fam = next((f for f in event["families"] if f["id"] == family_id), None)

    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id}", 404

    family_name = fam["family_name"]
    tickets = fam["tickets_total"]   # כמות כרטיסים מתוך TOT_FFAM

    return render_template(
        "confirm.html",
        family_name=family_name,
        tickets=tickets,
        event_name=event["event_name"],
        event_date=event["event_date"],
        event_time=event["event_time"],
        location=event["event_location"]
    )


# --------------------------------------------------------
# סימון מגיעים / לא מגיעים
# --------------------------------------------------------
@app.route("/update", methods=["POST"])
def update():

    family_name = request.form.get("family_name")
    qty = request.form.get("qty")
    status = request.form.get("status")

    return render_template(
        "thanks.html",
        family_name=family_name,
        qty=qty,
        status=status
    )


@app.route("/")
def home():
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
