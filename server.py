from flask import Flask, request, render_template
import requests

app = Flask(__name__)

ZEBRA_URL_GET = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_URL_UPDATE = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"

USERNAME = "IVAPP"
PASSWORD = "1q2w3e4r"

def get_event_family_data(event_id, family_id):
    return {
        "family_name": "משפחת כהן",
        "event_name": "מחזקים ומתחזקים",
        "date": "18/12/2025",
        "time": "18:00",
      "location": "תל אביב",

        "tickets": "4"
    }

@app.route("/confirm")
def confirm():
    family_id = request.args.get("family")
    event_id = request.args.get("event")
    data = get_event_family_data(event_id, family_id)
    return render_template("confirm.html", family_id=family_id, event_id=event_id, **data)

@app.route("/update")
def update():
    family_id = request.args.get("family")
    event_id = request.args.get("event")
    status = request.args.get("status")

    xml_body = f"""<?xml version='1.0' encoding='utf-8'?>
    <ROOT>
        <PERMISSION>
            <USERNAME>{USERNAME}</USERNAME>
            <PASSWORD>{PASSWORD}</PASSWORD>
        </PERMISSION>
        <CARD_TYPE>business_customer</CARD_TYPE>
        <IDENTIFIER><ID>{family_id}</ID></IDENTIFIER>
        <CUST_DETAILS></CUST_DETAILS>
        <CONNECTION_CARD_DETAILS>
            <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
            <KEY>ID</KEY>
            <VALUE>{event_id}</VALUE>
            <FIELDS><ARRI>{status}</ARRI></FIELDS>
        </CONNECTION_CARD_DETAILS>
    </ROOT>
    """.strip()

    requests.post(ZEBRA_URL_UPDATE, data=xml_body.encode("utf-8"),
                  headers={"Content-Type": "application/xml"})

    msg = "אישורך נקלט 💙" if status == "1" else "העדכון נקלט 🧡"
    return render_template("thanks.html", message=msg)

if __name__ == "__main__":
    app.run()
