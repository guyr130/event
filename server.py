from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests
from datetime import datetime
import threading

app = Flask(__name__)

# ======================
# CONFIG
# ======================
GOOGLE_SHEETS_WEBAPP_URL = ""  # אם ריק – ידלג
ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"
FIXED_DATE = "18/12/2025"

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

    # ערכי ברירת מחדל כדי למנוע Undefined
    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id,
        tickets=5,
        family_name="",
        event_name="",
        event_date="",
        location=""
    )

# ======================
# BACKGROUND INTEGRATIONS
# ======================
def send_integrations(payload):
    # ---- Google Sheets ----
    if GOOGLE_SHEETS_WEBAPP_URL:
        try:
            requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=10)
            print("Sheets: OK")
        except Exception as e:
            print("Sheets ERROR:", e)
    else:
        print("Sheets: False GOOGLE_SHEETS_WEBAPP_URL not configured")

    # ---- Zebra ----
    zebra_status = "אישרו" if payload["status"] == "yes" else "ביטלו"
    zebra_tickets = payload["tickets"] if payload["status"] == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
  <PERMISSION>
    <USERNAME>{ZEBRA_USER}</USERNAME>
    <PASSWORD>{ZEBRA_PASS}</PASSWORD>
  </PERMISSION>
  <CARD_TYPE>business_customer</CARD_TYPE>
  <IDENTIFIER>
    <ID>{payload["family_id"]}</ID>
  </IDENTIFIER>
  <CONNECTION_CARD_DETAILS>
    <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
    <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
    <KEY>ID</KEY>
    <VALUE>{payload["event_id"]}</VALUE>
    <FIELDS>
      <A_C>{zebra_status}</A_C>
      <A_D>{FIXED_DATE}</A_D>
      <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
    </FIELDS>
  </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        r = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=10
        )
        print("Zebra:", r.text)
    except Exception as e:
        print("Zebra ERROR:", e)

# ======================
# SUBMIT – UI SAFE
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    payload = {
        "timestamp": datetime.now().isoformat(),
        "event_id": data.get("event_id"),
        "family_id": data.get("family_id"),
        "status": data.get("status"),
        "tickets": int(data.get("tickets", 0)),
        "ip": request.remote_addr
    }

    # שולחים ברקע – לא חוסם UI
    threading.Thread(target=send_integrations, args=(payload,)).start()

    return redirect(
        url_for("thanks", status=payload["status"], qty=payload["tickets"])
    )

# ======================
# THANK YOU PAGE
# ======================
@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
