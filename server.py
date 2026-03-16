# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
import re
import io
import os
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
# GOOGLE DRIVE CONFIG
# ======================
DRIVE_FOLDER_ID = "17KgugUdSJe0a89ObQI7d7vjjHpEQj0a4"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}


# ======================
# HELPERS
# ======================
def extract_cards_safe(xml_text):
    cards = []
    for match in re.finditer(r"<CARD_CONNECTION_.*?>.*?</CARD_CONNECTION_.*?>", xml_text, re.DOTALL):
        try:
            card_xml = match.group(0).replace("&", "&amp;")
            cards.append(ET.fromstring(card_xml))
        except Exception:
            continue
    return cards


def allowed_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_extension(filename):
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


def delete_existing_family_files(drive_service, family_id):
    query = (
        f"'{DRIVE_FOLDER_ID}' in parents and trashed=false "
        f"and name contains '{family_id}.'"
    )

    result = drive_service.files().list(
        q=query,
        fields="files(id,name)"
    ).execute()

    for item in result.get("files", []):
        if item["name"].startswith(f"{family_id}."):
            drive_service.files().delete(fileId=item["id"]).execute()


def upload_file_to_drive(file_storage, family_id):
    drive_service = get_drive_service()

    original_name = file_storage.filename
    ext = get_extension(original_name)
    new_name = f"{family_id}.{ext}"

    delete_existing_family_files(drive_service, family_id)

    file_bytes = file_storage.read()
    file_stream = io.BytesIO(file_bytes)

    mime_type = file_storage.mimetype or "application/octet-stream"

    media = MediaIoBaseUpload(
        file_stream,
        mimetype=mime_type,
        resumable=False
    )

    metadata = {
        "name": new_name,
        "parents": [DRIVE_FOLDER_ID]
    }

    created = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name"
    ).execute()

    return created


# ======================
# EVENT BY ID
# ======================
def get_event_by_id(event_id):
    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>EVEFAM</CARD_TYPE_FILTER>
    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
    </FIELDS>

    <ID></ID>
    <CARD_TYPE></CARD_TYPE>
</ROOT>
""".strip()

    print("==== SENT SINGLE EVENT XML ====")
    print(xml_body)
    print("==== END SENT SINGLE EVENT XML ====")

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA EVENT REQUEST FAILED:", e)
        return None

    print("==== RAW SINGLE EVENT XML ====")
    print(raw_xml)
    print("==== END SINGLE EVENT XML ====")

    try:
        tree = ET.fromstring(raw_xml)
        card = tree.find(".//CARD")
        if card is None:
            print("SINGLE EVENT PARSE: CARD NOT FOUND")
            return None

        event_data = {
            "event_id": (card.findtext("ID") or "").strip(),
            "event_name": (card.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (card.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (card.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (card.findtext(".//FIELDS/EVE_LOC") or "").strip()
        }

        print("==== PARSED SINGLE EVENT ====")
        print(event_data)
        print("==== END PARSED SINGLE EVENT ====")

        return event_data
    except Exception as e:
        print("SINGLE EVENT PARSE FAILED:", e)
        return None


# ======================
# FAMILY EVENTS
# ======================
def get_family_events_for_confirm(family_id):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <ID_FILTER>
        <ID>{family_id}</ID>
    </ID_FILTER>

    <CONNECTION_CARD_DETAILS>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <FIELDS>
            <ID></ID>
            <EV_N></EV_N>
            <EV_D></EV_D>
            <EVE_HOUR></EVE_HOUR>
            <EVE_LOC></EVE_LOC>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
""".strip()

    print("==== FAMILY ID ====")
    print(family_id)
    print("==== END FAMILY ID ====")

    print("==== SENT FAMILY EVENTS XML ====")
    print(xml_body)
    print("==== END SENT FAMILY EVENTS XML ====")

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA FAMILY EVENTS REQUEST FAILED:", e)
        return []

    print("==== RAW FAMILY EVENTS XML ====")
    print(raw_xml)
    print("==== END FAMILY EVENTS XML ====")

    connections = []
    try:
        tree = ET.fromstring(raw_xml)
        connections = [el for el in tree.iter() if el.tag.startswith("CARD_CONNECTION_")]
        print("==== CONNECTION TAGS FOUND WITH ET ====")
        print(len(connections))
        for c in connections:
            print("CONNECTION TAG:", c.tag)
        print("==== END CONNECTION TAGS FOUND WITH ET ====")
    except Exception as e:
        print("ET PARSE FAILED:", e)
        connections = extract_cards_safe(raw_xml)
        print("==== CONNECTION TAGS FOUND WITH SAFE EXTRACT ====")
        print(len(connections))
        for c in connections:
            print("CONNECTION TAG:", c.tag)
        print("==== END CONNECTION TAGS FOUND WITH SAFE EXTRACT ====")

    events = []
    for conn in connections:
        event_data = {
            "event_id": (conn.findtext("ID") or "").strip(),
            "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (conn.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip()
        }

        print("==== PARSED EVENT ====")
        print(event_data)
        print("==== END PARSED EVENT ====")

        events.append(event_data)

    events = [e for e in events if e["event_id"] or e["event_name"]]

    print("==== FINAL EVENTS COUNT ====")
    print(len(events))
    print("==== FINAL EVENTS LIST ====")
    print(events)
    print("==== END FINAL EVENTS LIST ====")

    return events


# ======================
# HOME
# ======================
@app.route("/")
def home():
    return "HOME OK"


# ======================
# EVENTS PAGE DATA
# ======================
@app.route("/events")
def events_api():
    return jsonify([])


# ======================
# CONFIRM PAGE
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()

    print("==== /confirm CALLED ====")
    print("family_id =", family_id)
    print("event_id  =", event_id)
    print("==== END /confirm CALLED ====")

    if not family_id:
        return "Missing family_id", 400

    if event_id:
        ev = get_event_by_id(event_id)

        if not ev:
            return render_template(
                "confirm.html",
                family_id=family_id,
                event_id="",
                event_name="",
                event_date="",
                event_time="",
                location="",
                has_events=False,
                error=""
            )

        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id=ev["event_id"],
            event_name=ev["event_name"],
            event_date=ev["event_date"],
            event_time=ev["event_time"],
            location=ev["location"],
            has_events=True,
            error=""
        )

    events = get_family_events_for_confirm(family_id)

    if not events:
        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id="",
            event_name="",
            event_date="",
            event_time="",
            location="",
            has_events=False,
            error=""
        )

    if len(events) == 1:
        ev = events[0]
        return render_template(
            "confirm.html",
            family_id=family_id,
            event_id=ev["event_id"],
            event_name=ev["event_name"],
            event_date=ev["event_date"],
            event_time=ev["event_time"],
            location=ev["location"],
            has_events=True,
            error=""
        )

    return render_template(
        "select_event.html",
        family_id=family_id,
        family_name="",
        events=events
    )


# ======================
# SUBMIT RESPONSE
# ======================
@app.route("/submit_response", methods=["POST"])
def submit_response():
    family_id = request.form.get("family_id", "").strip()
    event_id = request.form.get("event_id", "").strip()
    status = request.form.get("status", "").strip()
    qty = request.form.get("qty", "1").strip()

    print("==== SUBMIT RESPONSE ====")
    print("family_id =", family_id)
    print("event_id  =", event_id)
    print("status    =", status)
    print("qty       =", qty)
    print("==== END SUBMIT RESPONSE ====")

    if not family_id:
        return "Missing family_id", 400

    if status not in {"yes", "no"}:
        return "Invalid status", 400

    if status == "yes":
        try:
            qty_num = int(qty)
            if qty_num < 1:
                qty_num = 1
        except Exception:
            qty_num = 1
    else:
        qty_num = 0

    photo = request.files.get("photo")

    if photo and photo.filename:
        print("==== UPLOAD FILE DETECTED ====")
        print("filename =", photo.filename)
        print("mimetype =", photo.mimetype)
        print("==== END UPLOAD FILE DETECTED ====")

        if not allowed_file(photo.filename):
            ev = get_event_by_id(event_id) if event_id else None
            return render_template(
                "confirm.html",
                family_id=family_id,
                event_id=event_id,
                event_name=(ev["event_name"] if ev else ""),
                event_date=(ev["event_date"] if ev else ""),
                event_time=(ev["event_time"] if ev else ""),
                location=(ev["location"] if ev else ""),
                has_events=True if ev else False,
                error="סוג הקובץ לא נתמך. אפשר להעלות JPG / JPEG / PNG / WEBP / PDF בלבד."
            )

        try:
            upload_result = upload_file_to_drive(photo, family_id)
            print("==== UPLOAD TO DRIVE SUCCESS ====")
            print(upload_result)
            print("==== END UPLOAD TO DRIVE SUCCESS ====")
        except Exception as e:
            print("UPLOAD TO DRIVE FAILED:", e)
            ev = get_event_by_id(event_id) if event_id else None
            return render_template(
                "confirm.html",
                family_id=family_id,
                event_id=event_id,
                event_name=(ev["event_name"] if ev else ""),
                event_date=(ev["event_date"] if ev else ""),
                event_time=(ev["event_time"] if ev else ""),
                location=(ev["location"] if ev else ""),
                has_events=True if ev else False,
                error="אירעה שגיאה בהעלאת הקובץ. נסו שוב."
            )

    return render_template(
        "thanks.html",
        status=status,
        qty=qty_num,
        event_id=event_id,
        family_id=family_id
    )


# ======================
# FILE TOO LARGE
# ======================
@app.errorhandler(413)
def too_large(e):
    return "הקובץ גדול מדי. אפשר להעלות עד 5MB בלבד.", 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
