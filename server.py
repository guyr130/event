# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, render_template
import requests
from datetime import datetime
import os

app = Flask(__name__)

# =============================
# ZEBRA CONFIG
# =============================
ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# =============================
# HOME (Render health check)
# =============================
@app.route("/")
def home():
    return "OK"

# =============================
# CONFIRM PAGE
# =============================
@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    # ⚠️ כאן אתה כבר שולף נכון – משאיר פשוט
    return render_template(
        "confirm.html",
        event_id=event_id,
        zebra_family_id=family_id,
        family_name="בדיקה",
        tickets=2,
        event_name="אירוע בדיקה",
        event_date="17/12/2025",
        location="ירושלים"
    )

# =============================
# SUBMIT
# =============================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    family_id = data["family_id"]
    event_id = data["event_id"]
    status = data["status"]
    tickets = int(data["tickets"])

    # =============================
    # ⚠️ זמני – בדיקה קשיחה
    # =============================
    connection_id = 138  # CARD_CONNECTION_ID של ASKEV

    today = datetime.now().strftime("%d/%m/%Y")
    ac_value = "אישרו" if status == "yes" else "ביטלו"
    arrive_value = tickets if status == "yes" else 0

    xml = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

        <KEY>ID</KEY>
        <VALUE>{connection_id}</VALUE>

        <CON_FIELDS>
            <A_C>{ac_value}</A_C>
            <A_D>{today}</A_D>
            <NO_ARIVE>{arrive_value}</NO_ARIVE>
        </CON_FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
""".strip()

    print(">>> UPDATE ASKEV <<<")
    print(xml)

    res = requests.post(
        ZEBRA_URL,
        data=xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"}
    )

    print("[ZEBRA RESPONSE]")
    print(res.text)

    return jsonify({"success": True})

# =============================
# THANKS
# =============================
@app.route("/thanks")
def thanks():
    status = request.args.get("status")
    qty = request.args.get("qty")
    return f"תודה! סטטוס: {status} | כמות: {qty}"

# =============================
# RUN
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
