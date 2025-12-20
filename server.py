from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================

GOOGLE_SHEETS_WEBAPP_URL = "https://YOUR_REAL_SHEETS_URL_HERE"

ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"
FIXED_DATE = "18/12/2025"

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK"

# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    return render_template(
        "confirm.html",
        event_id=event_id,
        family_id=family_id,
        tickets=5  # רק כדי שה־HTML לא ייפול
    )

# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json or {}

    event_id = data.get("event_id")
    family_id = data.get("family_id")
    status = data.get("status")
    tickets = int(data.get("tickets", 0))

    # ---- Google Sheets ----
    if GOOGLE_SHEETS_WEBAPP_URL.startswith("http"):
        try:
            requests.post(
                GOOGLE_SHEETS_WEBAPP_URL,
                json={
                    "timestamp": datetime.now().isoformat(),
                    "event_id": event_id,
                    "family_id": family_id,
                    "status": status,
                    "tickets": tickets
                },
                timeout=10
            )
        except Exception as e:
            print("Sheets ERROR:", e)

    # ---- Zebra ----
    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
  <PERMISSION>
    <USERNAME>{ZEBRA_USER}</USERNAME>
    <PASSWORD>{ZEBRA_PASS}</PASSWORD>
  </PERMISSION>
  <CARD_TYPE>business_customer</CARD_TYPE>
  <IDENTIFIER><ID>{family_id}</ID></IDENTIFIER>
  <CONNECTION_CARD_DETAILS>
    <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
    <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
    <KEY>ID</KEY>
    <VALUE>{event_id}</VALUE>
    <FIELDS>
      <A_C>{"אישרו" if status=="yes" else "ביטלו"}</A_C>
      <A_D>{FIXED_DATE}</A_D>
      <NO_ARIVE>{tickets if status=="yes" else 0}</NO_ARIVE>
    </FIELDS>
  </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=10
        )
    except Exception as e:
        print("Zebra ERROR:", e)

    return jsonify(success=True)

# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")
    return render_template("thanks.html", status=status, qty=qty)

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
