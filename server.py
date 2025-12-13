from flask import Flask, request, render_template
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# ------ פרטי חיבור לזברה ------
ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
USERNAME = "IVAPP"
PASSWORD = "1q2w3e4r"


# ========================================================
#   שליפה מה־API של זברה: אירוע + משפחות
# ========================================================
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

    # שליחת POST לזברה
    response = requests.post(
        ZEBRA_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"}
    )

    raw = response.text.strip()
    print("===== ZEBRA RAW RESPONSE =====")
    print(raw)
    print("===== END RESPONSE =====")

    # אם לא חזר XML תקין
    if not raw.startswith("<"):
        return {"error": f"Invalid XML response: {raw}"}

    tree = ET.fromstring(raw)

    # שדות אירוע
    ev_name = tree.findtext(".//EV_N", "")
    ev_date = tree.findtext(".//EV_D", "")
    ev_time = tree.findtext(".//EVE_HOUR", "")
    ev_loc = tree.findtext(".//EVE_LOC", "")

    # ----------------------------------------------------
    # משפחות – תגיות דינמיות CARD_CONNECTION_XXXXX
    # ----------------------------------------------------
    families = []
    for node in tree.findall(".//*"):
        if node.tag.startswith("CARD_CONNECTION_"):
            fam_id = node.findtext("ID", "")
            name = node.findtext("FIELDS/CO_NAME", "")
            tickets = node.findtext("CON_FIELDS/TOT_FFAM", "0")
            approved = node.findtext("CON_FIELDS/PROV", "0")

            families.append({
                "id": fam_id,
                "name": name,
                "tickets": int(tickets),
                "approved": approved
            })

    return {
        "event_name": ev_name,
        "event_date": ev_date,
        "event_time": ev_time,
        "event_location": ev_loc,
        "families": families
    }


# ========================================================
#   עמוד אישור הגעה
# ========================================================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "חסר event_id או family_id", 400

    data = get_event_data(event_id)

    if "error" in data:
        return f"שגיאה בשליפת נתונים מזברה: {data['error']}", 500

    fam = next((f for f in data["families"] if f["id"] == family_id), None)

    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id}"

    return render_template(
        "confirm.html",
        family_name=fam["name"],
        tickets=fam["tickets"],
        event_name=data["event_name"],
        event_date=data["event_date"],
        event_time=data["event_time"],
        location=data["event_location"],
        family_id=family_id,
        event_id=event_id
    )


@app.route("/")
def home():
    return "המערכת פעילה ✔️"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
