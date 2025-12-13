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

    # ---- event data ----
    ev_name = card.findtext(".//EV_N", default="")
    ev_date_raw = card.findtext(".//EV_D", default="")
    ev_hour = card.findtext(".//EVE_HOUR", default="")
    ev_loc = card.findtext(".//EVE_LOC", default="")

    # ---- format date ----
    try:
        dt = datetime.strptime(ev_date_raw, "%d/%m/%Y")
        weekday_eng = dt.strftime("%A")
        weekdays = {
            "Sunday": "יום א'",
            "Monday": "יום ב'",
            "Tuesday": "יום ג'",
            "Wednesday": "יום ד'",
            "Thursday": "יום ה'",
            "Friday": "יום ו'",
            "Saturday": "יום ש'"
        }
        weekday = weekdays.get(weekday_eng, "")
        date_fmt = dt.strftime("%d.%m")
    except:
        weekday = ""
        date_fmt = ev_date_raw

    # ---- families ----
    families = []
    con_root = card.find("CONNECTIONS_CARDS")

    if con_root is not None:
        for connection in con_root:
            fam_id = connection.findtext("ID")
            fam_name = connection.findtext(".//CO_NAME", default="")
            tickets = connection.findtext(".//TOT_FFAM", default="0")
            prov = connection.findtext(".//PROV", default="0")

            families.append({
                "id": fam_id,
                "name": fam_name,
                "tickets": int(tickets),
                "approved": prov == "1"
            })

    return {
        "name": ev_name,
        "date": date_fmt,
        "weekday": weekday,
        "time": ev_hour,
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

    fam = next((f for f in data["families"]
                if f["id"] == family_id and f["approved"]), None)

    if fam is None:
        return f"לא נמצאה משפחה {family_id} באירוע {event_id} (או שאינה מאושרת)"

    return render_template(
        "confirm.html",
        family_name=fam["name"],
        tickets=fam["tickets"],
        event_name=data["name"],
        event_date=f"{data['weekday']} · {data['date']} · {data['time']}",
        event_time=data["time"],
        location=data["location"]
    )


@app.route("/thanks")
def thanks():
    status = request.args.get("s")
    qty = request.args.get("q")

    if status == "yes":
        message = "אישורכם נקלט"
        sub = f"כמות שאושרה: {qty}"
    else:
        message = "העדכון נקלט"
        sub = "נתראה באירועים אחרים 🧡"

    return render_template("thanks.html", message=message, sub=sub)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
