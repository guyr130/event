from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================

# Google Sheets – תשאיר את הכתובת האמיתית שלך
GOOGLE_SHEETS_WEBAPP_URL = "PASTE_YOUR_GOOGLE_SHEETS_WEBAPP_URL_HERE"

# Zebra UPDATE
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# כאן תשנה לתאריך האירוע האמיתי – או שתעביר אותו כפרמטר אם יש כמה אירועים
EVENT_DATE = "20/12/2025"  # שונה מ-18 ל-20 כמו בדוגמה שלך

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK – server is running"


# ======================
# CONFIRM PAGE
# ======================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id
    )


# ======================
# SUBMIT – כאן מתבצע העדכון ל-Zebra
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")        # "yes" או "no"
    tickets = int(data.get("tickets", 0))

    if not event_id or not family_id or status not in ["yes", "no"]:
        return jsonify({"success": False, "error": "Invalid data"}), 400

    # ======================
    # 1. שמירה ב-Google Sheets (לא משנים)
    # ======================
    sheet_payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": event_id,
        "family_id": family_id,
        "status": status,
        "tickets": tickets,
        "user_agent": request.headers.get("User-Agent", ""),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr)
    }

    try:
        r = requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=sheet_payload, timeout=10)
        print("Google Sheets response:", r.status_code)
    except Exception as e:
        print("Google Sheets ERROR:", e)

    # ======================
    # 2. עדכון ב-Zebra CRM – בדיוק כמו בקובץ הדוגמה שלך
    # ======================
    zebra_status = "אישרו" if status == "yes" else "ביטלו"
    zebra_tickets = tickets if status == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CUST_DETAILS>
    </CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{zebra_status}</A_C>
            <A_D>{EVENT_DATE}</A_D>
            <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>"""

    try:
        zr = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15
        )
        print("Zebra response status:", zr.status_code)
        print("Zebra response body:", zr.text.strip())
    except Exception as e:
        print("Zebra ERROR:", str(e))

    return jsonify({"success": True})


# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
