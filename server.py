# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import os
import io
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# GOOGLE APPS SCRIPT (LOG)
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxYOTETwFoJXbFHxNUwh3-AbwUsdnQ680194wn8svCFHE7c9zFreRI9hQhcDrPsAqM1/exec"

# ======================
# GOOGLE DRIVE CONFIG
# ======================
DRIVE_FOLDER_ID = "17KgugUdSJe0a89ObQI7d7vjjHpEQj0a4"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}

# ======================
# IDEMPOTENCY (ANTI DOUBLE-CLICK)
# ======================
recent_requests = {}
IDEMPOTENCY_WINDOW = 15  # seconds


def is_duplicate(event_id, family_id, status, tickets):
    now = time.time()
    key = f"{event_id}|{family_id}|{status}|{tickets}"

    expired = [k for k, v in recent_requests.items() if now - v > IDEMPOTENCY_WINDOW]
    for k in expired:
        del recent_requests[k]

    if key in recent_requests:
        return True

    recent_requests[key] = now
    return False


def zebra_post(xml_body: str, timeout: int = 15) -> str:
    r = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=timeout
    )
    return r.text


def parse_ddmmyyyy(date_str: str):
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except Exception:
        return None


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def file_ext(filename: str) -> str:
    return filename.rsplit(".", 1)[1].lower()


def get_drive_service():
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_json:
        raise ValueError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable")

    info = json.loads(raw_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def delete_existing_family_files(drive_service, family_id: str):
    query = (
        f"'{DRIVE_FOLDER_ID}' in parents and trashed=false "
        f"and name contains '{family_id}.'"
    )

    result = drive_service.files().list(
        q=query,
        fields="files(id,name)"
    ).execute()

    for item in result.get("files", []):
        name = item.get("name", "")
        if name.startswith(f"{family_id}."):
            drive_service.files().delete(fileId=item["id"]).execute()


def upload_file_to_drive(file_storage, family_id: str):
    ext = file_ext(file_storage.filename)
    new_name = f"{family_id}.{ext}"

    drive_service = get_drive_service()
    delete_existing_family_files(drive_service, family_id)

    file_bytes = file_storage.read()
    file_stream = io.BytesIO(file_bytes)

    media = MediaIoBaseUpload(
        file_stream,
        mimetype=file_storage.mimetype or "application/octet-stream",
        resumable=False
    )

    metadata = {
        "name": new_name,
        "parents": [DRIVE_FOLDER_ID]
    }

    created = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink"
    ).execute()

    return created


def get_family_events(family_id: str):
    """
    מחזיר:
    {
      family_id, family_name,
      events: [{event_id,event_name,event_date,event_time,location,tickets,prov}, ...]
    }
    """
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{family_id}</ID_FILTER>

    <FIELDS>
        <CO_NAME></CO_NAME>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

            <FIELDS>
                <ID></ID>
                <EV_N></EV_N>
                <EV_D></EV_D>
                <EVE_HOUR></EVE_HOUR>
                <EVE_LOC></EVE_LOC>
            </FIELDS>

            <CON_FIELDS>
                <TOT_FFAM></TOT_FFAM>
                <PROV></PROV>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    text = zebra_post(xml_body)
    tree = ET.fromstring(text)

    card = tree.find(".//CARDS/CARD")
    if card is None:
        return None

    family_name = (card.findtext(".//FIELDS/CO_NAME") or "").strip()

    events = []
    connections = card.find(".//CONNECTIONS_CARDS")
    if connections is not None:
        for el in list(connections):
            if not el.tag.startswith("CARD_CONNECTION_"):
                continue

            event_id = (el.findtext("ID") or "").strip()
            event_name = (el.findtext(".//FIELDS/EV_N") or "").strip()
            event_date = (el.findtext(".//FIELDS/EV_D") or "").strip()
            event_time = (el.findtext(".//FIELDS/EVE_HOUR") or "").strip()
            location = (el.findtext(".//FIELDS/EVE_LOC") or "").strip()

            tickets_raw = (el.findtext(".//CON_FIELDS/TOT_FFAM") or "0").strip()
            try:
                tickets = int(tickets_raw) if tickets_raw else 0
            except Exception:
                tickets = 0

            prov = (el.findtext(".//CON_FIELDS/PROV") or "").strip()

            events.append({
                "event_id": event_id,
                "event_name": event_name,
                "event_date": event_date,
                "event_time": event_time,
                "location": location,
                "tickets": tickets,
                "prov": prov
            })

    return {
        "family_id": family_id,
        "family_name": family_name,
        "events": events
    }


def filter_events(events):
    """
    שני תנאים:
    1) מאושר (PROV == "1")
    2) תאריך היום ובעתיד
    """
    today = datetime.today().date()
    valid = []

    for ev in events:
        if str(ev.get("prov", "")).strip() != "1":
            continue

        d = parse_ddmmyyyy(ev.get("event_date", ""))
        if not d:
            continue

        if d < today:
            continue

        valid.append(ev)

    def sort_key(x):
        d = parse_ddmmyyyy(x.get("event_date", "")) or today
        t = (x.get("event_time") or "00:00").strip()
        return (d, t)

    valid.sort(key=sort_key)
    return valid


# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = (request.args.get("family_id") or "").strip()
    event_id = (request.args.get("event_id") or "").strip()

    if not family_id:
        return "Missing family_id", 400

    fam = get_family_events(family_id)
    if not fam:
        return "Family not found in Zebra", 404

    family_name = fam["family_name"]
    valid_events = filter_events(fam["events"])

    if not event_id:
        if len(valid_events) == 0:
            return "אין אירועים זמינים למשפחה זו", 404

        if len(valid_events) == 1:
            ev = valid_events[0]
            return render_template(
                "confirm.html",
                family_id=family_id,
                family_name=family_name,
                event_id=ev["event_id"],
                event_name=ev["event_name"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                location=ev["location"],
                tickets=ev["tickets"]
            )

        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name=family_name,
            events=valid_events
        )

    chosen = next((e for e in valid_events if str(e.get("event_id", "")).strip() == event_id), None)
    if not chosen:
        return "האירוע לא נמצא / לא מאושר / תאריך עבר", 404

    return render_template(
        "confirm.html",
        family_id=family_id,
        family_name=family_name,
        event_id=chosen["event_id"],
        event_name=chosen["event_name"],
        event_date=chosen["event_date"],
        event_time=chosen["event_time"],
        location=chosen["location"],
        tickets=chosen["tickets"]
    )


# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    event_id = str(request.form.get("event_id") or "").strip()
    family_id = str(request.form.get("family_id") or "").strip()
    status = str(request.form.get("status") or "").strip()  # yes/no
    tickets_raw = str(request.form.get("tickets") or "0").strip()

    family_name = str(request.form.get("family_name") or "").strip()
    event_name = str(request.form.get("event_name") or "").strip()

    try:
        tickets = int(tickets_raw or 0)
    except Exception:
        tickets = 0

    if not event_id or not family_id or status not in ("yes", "no"):
        return jsonify({"success": False, "error": "Missing parameters"}), 400

    if status == "yes" and tickets < 1:
        return jsonify({"success": False, "error": "Missing tickets"}), 400

    if status == "no":
        tickets = 0

    if is_duplicate(event_id, family_id, status, tickets):
        return jsonify({"success": True, "duplicate": True})

    uploaded_file = request.files.get("photo")
    uploaded_drive_info = None

    if uploaded_file and uploaded_file.filename:
        if not allowed_file(uploaded_file.filename):
            return jsonify({
                "success": False,
                "error": "סוג קובץ לא נתמך. ניתן להעלות JPG / JPEG / PNG / WEBP / PDF בלבד."
            }), 400

        try:
            uploaded_drive_info = upload_file_to_drive(uploaded_file, family_id)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"שגיאה בהעלאת הקובץ ל-Google Drive: {str(e)}"
            }), 500

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    status_he = "אישרו" if status == "yes" else "ביטלו"

    payload = {
        "timestamp": timestamp,
        "family_id": family_id,
        "family_name": family_name,
        "event_id": event_id,
        "event_name": event_name,
        "status": status_he,
        "tickets": tickets
    }

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=20
        )
        return jsonify({
            "success": True,
            "google_status": r.status_code,
            "google_body": (r.text or "")[:400],
            "uploaded_file": uploaded_drive_info.get("name") if uploaded_drive_info else ""
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = request.args.get("status", "")
    qty = request.args.get("qty", "0")
    event_id = request.args.get("event_id", "")
    family_id = request.args.get("family_id", "")
    return render_template("thanks.html", status=status, qty=qty, event_id=event_id, family_id=family_id)


# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
