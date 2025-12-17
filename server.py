from flask import Flask, request, render_template, redirect, url_for
import requests
import datetime

app = Flask(__name__)

GOOGLE_SHEET_WEBHOOK = "PASTE_HERE_FULL_HTTPS_WEBHOOK_URL"

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "17/12/2025"

@app.route("/confirm")
def confirm():
    event_id = request.args.get("event_id")
    family_id = request.args.get("family_id")

    if not event_id or not family_id:
        return "Missing parameters", 400

    return render_template(
        "confirm.html",
        event_id=event_id,
        zebra_family_id=family_id,
        family_name=f"משפחה {family_id}",
        tickets=2,
        event_name=f"אירוע {event_id}",
        event_date=FIXED_DATE,
        location="ירושלים"
    )

@app.route("/submit", methods=["POST"])
def submit():
    # =========================
    # DEBUG: מה באמת הגיע לשרת
    # =========================
    raw_body = request.get_data(as_text=True)  # לא OCR, זה גוף הבקשה
    json_data = request.get_json(silent=True)  # לא מכריח JSON

    print("===== SUBMIT DEBUG =====")
    print("Content-Type:", request.content_type)
    print("Args:", dict(request.args))
    print("Form:", dict(request.form))
    print("JSON:", json_data)
    print("Raw body:", raw_body[:1000])  # חותך כדי לא לפוצץ לוגים
    print("========================")

    # =========================
    # קליטה חזקה: JSON / FORM / QUERY
    # =========================
    event_id = None
    family_id = None
    status = None
    tickets = None

    # 1) JSON
    if isinstance(json_data, dict):
        event_id = json_data.get("event_id")
        family_id = json_data.get("family_id")
        status = json_data.get("status")
        tickets = json_data.get("tickets")

    # 2) FORM
    if not event_id or not family_id:
        event_id = event_id or request.form.get("event_id")
        family_id = family_id or request.form.get("family_id")
        status = status or request.form.get("status")
        tickets = tickets if tickets is not None else request.form.get("tickets")

    # 3) QUERYSTRING
    if not event_id or not family_id:
        event_id = event_id or request.args.get("event_id")
        family_id = family_id or request.args.get("family_id")
        status = status or request.args.get("status")
        tickets = tickets if tickets is not None else request.args.get("tickets")

    status = status or "no"
    try:
        tickets = int(tickets or 0)
    except Exception:
        tickets = 0

    if not event_id or not family_id:
        # זה מה שיצר לך 400 — עכשיו זה יהיה ברור בלוג מה חסר
        return "Missing family_id or event_id", 400

    # =========================
    # Google Sheets (לא נוגע לוגיקה)
    # =========================
    try:
        sheet_payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_id": str(event_id),
            "family_id": str(family_id),
            "status": status,
            "tickets": tickets,
            "user_agent": request.headers.get("User-Agent"),
            "ip": request.remote_addr
        }
        r = requests.post(GOOGLE_SHEET_WEBHOOK, json=sheet_payload, timeout=5)
        print("===== SENT TO GOOGLE SHEETS =====")
        print(sheet_payload)
        print("Sheets response:", r.status_code, r.text)
        print("================================")
    except Exception as e:
        print("Sheets error:", e)

    # =========================
    # Zebra XML — כמו פוסטמן + תאריך קבוע
    # =========================
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
<A_D>{FIXED_DATE}</A_D>
<NO_ARIVE>{zebra_tickets}</NO_ARIVE>
</FIELDS>
</CONNECTION_CARD_DETAILS>
</ROOT>
"""

    try:
        print("===== ZEBRA REQUEST =====")
        print(zebra_xml)

        zr = requests.post(
            ZEBRA_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            timeout=10
        )

        print("===== ZEBRA RESPONSE =====")
        print(zr.text)
    except Exception as e:
        print("Zebra error:", e)

    return redirect(url_for("thanks", status=status, qty=zebra_tickets))

@app.route("/thanks")
def thanks():
    return render_template(
        "thanks.html",
        status=request.args.get("status"),
        qty=request.args.get("qty")
    )

@app.route("/")
def root():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
