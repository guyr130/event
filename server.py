# -*- coding: utf-8 -*-
import requests
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request
from datetime import datetime

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
                <FIELDS>
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

    response = requests.post(ZEBRA_URL, data=xml_body.encode("utf-8"))
    tree = ET.fromstring(response.text)

    card = tree.find(".//CARD")
    if card is None:
        return None

    # ---- אירוע ----
    ev_name = card.findtext(".//EV_N", default="")
    ev_date_raw = card.findtext(".//EV_D", default="")
    ev_hour = card.findtext(".//EVE_HOUR", default="")
    ev_loc = card.findtext(".//EVE_LOC", default="")

    # ---- המרת תאריך לפורמט יפה ----
    # מגיע כ- DD/MM/YYYY
    try:
        dt = datetime.strptime(ev_date_raw, "%d/%m/%Y")
        weekday_name = dt.strftime("%A")  # Sunday, Monday...
        weekdays_he = {
            "Sunday": "יום א'",
            "Monday": "יום ב'",
            "Tuesday": "יום ג'",
            "Wednesday": "יום ד'",
            "Thursday": "יום ה'",
            "Friday": "יום ו'",
            "Saturday": "יום ש'"
        }
        weekday_he = weekdays_he.get(weekday_name, "")
        date_formatted = dt.strftime("%d.%m")  # 21.12
    except:
        weekday_he = ""
        date_formatted = ev_date_raw

    # ---- משפחות ----
    families = []
    for con in card.findall(".//CARD_CONNECTION_*/"):
        pass  # לא בשימוש – רק לוודא שאין זבל

    for c in card.find("CONNECTIONS_CARDS"):
        fam_id = c.findtext("ID")
        name = c.findtext(".//CO_NAME", default="")
        tickets = c.findtext(".//TOT_FFAM", default="0")
        prov = c.findtext(".//PROV", default="0")
        families.append({
            "id": fam_id,
            "name": name,
            "tickets": int(tickets),
            "approved": prov == "1"
        })

    return {
        "name": ev_name,
        "date": date_formatted,
        "weekday": weekday_he,
        "time": ev_hour,     # כאן כבר נשמר כמו שצריך "12:00"
        "location": ev_loc,
        "families": families
    }


@app.route("/")
def home():
    return "המערכת פעילה ✔️"


@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "חסר event_id או family_id"

    data = get_event_data(event_id)
    if not data:
        return f"שגיאה בטעינת האירוע {event_id}"

    # מציאת המשפחה
    fam = next((f for f in data["families"]
                if f["id"] == family_id and f["approved"]), None)

    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id} (או שאינה מאושרת)"

    return render_template(
        "confirm.html",
        family_name=fam["name"],
        tickets=fam["tickets"],
        event_name=data["name"],
        event_date=data["weekday"] + " · " + data["date"] + " · " + data["time"],
        event_time=data["time"],
        location=data["location"]
    )


@app.route("/thanks")
def thanks():
    status = request.args.get("s")
    qty = request.args.get("q")

    if status == "yes":
        message = f"אישורכם נקלט"
        sub = f"כמות שאושרה: {qty}"
    else:
        message = "העדכון נקלט"
        sub = "נתראה באירועים אחרים 🧡"

    return render_template("thanks.html", message=message, sub=sub)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
