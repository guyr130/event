# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for
import requests
import xml.etree.ElementTree as ET
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ======================
# APP CONFIG
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "pdf"
}
ALLOWED_MIME_PREFIXES = ("image/",)
ALLOWED_MIME_EXACT = {
    "application/pdf"
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15MB

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

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

def allowed_file(file_storage):
    filename = (file_storage.filename or "").strip()
    if not filename or "." not in filename:
        return False

    ext = filename.rsplit(".", 1)[1].lower()
    mimetype = (file_storage.mimetype or "").lower()

    if ext in ALLOWED_EXTENSIONS:
        return True

    if mimetype in ALLOWED_MIME_EXACT:
        return True

    if any(mimetype.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        return True

    return False

def build_photo_filename(family_id, event_id, original_filename):
    ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else "bin"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_family = re.sub(r"[^0-9A-Za-z_-]", "", family_id)
    safe_event = re.sub(r"[^0-9A-Za-z_-]", "", event_id) if event_id else "noevent"
    return f"{safe_family}_{safe_event}_{ts}.{ext}"

def extract_first_nonempty_text(root, candidate_tags):
    for elem in root.iter():
        tag_name = elem.tag.split("}")[-1].upper()
        if tag_name in candidate_tags:
            value = (elem.text or "").strip()
            if value:
                return value
    return ""

# ======================
# שליפת פרטי משפחה
# ======================
def get_family_details(family_id):
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

    <FIELDS>
        <FAMILY_NAME></FAMILY_NAME>
        <LAST_NAME></LAST_NAME>
        <NAME></NAME>
        <FIRST_NAME></FIRST_NAME>
        <CUST_NAME></CUST_NAME>
        <BUSINESS_NAME></BUSINESS_NAME>
    </FIELDS>
</ROOT>
""".strip()

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA FAMILY REQUEST FAILED:", e)
        return {
            "family_id": family_id,
            "family_name": ""
        }

    print("==== RAW FAMILY XML ====")
    print(raw_xml)
    print("==== END FAMILY XML ====")

    family_name = ""

    try:
        tree = ET.fromstring(raw_xml)
        family_name = extract_first_nonempty_text(
            tree,
            {
                "FAMILY_NAME",
                "LAST_NAME",
                "NAME",
                "FIRST_NAME",
                "CUST_NAME",
                "BUSINESS_NAME"
            }
        )
    except Exception as e:
        print("FAMILY PARSE FAILED:", e)

    return {
        "family_id": family_id,
        "family_name": family_name
    }

# ======================
# שליפת אירועים למשפחה
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

    try:
        res = requests.post(
            ZEBRA_GET_URL,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=20
        )
        raw_xml = res.text
    except Exception as e:
        print("ZEBRA EVENTS REQUEST FAILED:", e)
        return []

    print("==== RAW EVENTS XML ====")
    print(raw_xml)
    print("==== END EVENTS XML ====")

    try:
        tree = ET.fromstring(raw_xml)
        connections = [el for el in tree.iter() if el.tag.startswith("CARD_CONNECTION_")]
    except Exception:
        connections = extract_cards_safe(raw_xml)

    events = []
    for conn in connections:
        events.append({
            "event_id": (conn.findtext("ID") or "").strip(),
            "event_name": (conn.findtext(".//FIELDS/EV_N") or "").strip(),
            "event_date": (conn.findtext(".//FIELDS/EV_D") or "").strip(),
            "event_time": (conn.findtext(".//FIELDS/EVE_HOUR") or "").strip(),
            "location": (conn.findtext(".//FIELDS/EVE_LOC") or "").strip()
        })

    return events

# ======================
# CONFIRM PAGE
# ======================
@app.route("/confirm")
def confirm():
    family_id = request.args.get("family_id", "").strip()
    event_id = request.args.get("event_id", "").strip()
    upload_success = request.args.get("upload_success", "").strip()
    upload_error = request.args.get("upload_error", "").strip()
    uploaded_file = request.args.get("uploaded_file", "").strip()

    if not family_id:
        return "Missing family_id", 400

    family = get_family_details(family_id)
    family_name = family.get("family_name", "").strip()

    events = get_family_events_for_confirm(family_id)

    if not events:
        return render_template(
            "confirm.html",
            family_id=family_id,
            family_name=family_name,
            event_id="",
            event_name="",
            event_date="",
            event_time="",
            location="",
            has_events=False,
            upload_success=upload_success,
            upload_error=upload_error,
            uploaded_file=uploaded_file
        )

    if not event_id:
        if len(events) == 1:
            ev = events[0]
            return render_template(
                "confirm.html",
                family_id=family_id,
                family_name=family_name,
                event_id=ev["event_id"],
                event_name=ev["event_name"],
                event_date=ev["event_date"],
                event_time=ev["event_time"],
                location=ev["location"],
                has_events=True,
                upload_success=upload_success,
                upload_error=upload_error,
                uploaded_file=uploaded_file
            )

        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name=family_name,
            events=events
        )

    chosen = next((e for e in events if e["event_id"] == event_id), None)

    if not chosen:
        return render_template(
            "confirm.html",
            family_id=family_id,
            family_name=family_name,
            event_id="",
            event_name="",
            event_date="",
            event_time="",
            location="",
            has_events=False,
            upload_success=upload_success,
            upload_error=upload_error,
            uploaded_file=uploaded_file
        )

    return render_template(
        "confirm.html",
        family_id=family_id,
        family_name=family_name,
        event_id=chosen["event_id"],
        event_name=chosen["event_name"],
        event_date=chosen["event_date"],
        event_time=chosen["event_time"],
        location=chosen["location"],
        has_events=True,
        upload_success=upload_success,
        upload_error=upload_error,
        uploaded_file=uploaded_file
    )

# ======================
# PHOTO UPLOAD
# ======================
@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    family_id = request.form.get("family_id", "").strip()
    event_id = request.form.get("event_id", "").strip()

    if not family_id:
        return "Missing family_id", 400

    if "photo" not in request.files:
        return redirect(url_for(
            "confirm",
            family_id=family_id,
            event_id=event_id,
            upload_error="לא נבחר קובץ"
        ))

    file = request.files["photo"]

    if not file or not (file.filename or "").strip():
        return redirect(url_for(
            "confirm",
            family_id=family_id,
            event_id=event_id,
            upload_error="לא נבחר קובץ"
        ))

    if not allowed_file(file):
        return redirect(url_for(
            "confirm",
            family_id=family_id,
            event_id=event_id,
            upload_error="מותר להעלות קובץ תמונה או PDF"
        ))

    try:
        original_filename = secure_filename(file.filename or "upload.bin")
        if "." not in original_filename:
            if file.mimetype == "application/pdf":
                original_filename += ".pdf"
            else:
                original_filename += ".jpg"

        new_filename = build_photo_filename(family_id, event_id, original_filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        file.save(save_path)

        print(f"PHOTO SAVED: family_id={family_id}, event_id={event_id}, file={new_filename}, mimetype={file.mimetype}")

        return redirect(url_for(
            "confirm",
            family_id=family_id,
            event_id=event_id,
            upload_success="1",
            uploaded_file=new_filename
        ))

    except Exception as e:
        print("UPLOAD FAILED:", e)
        return redirect(url_for(
            "confirm",
            family_id=family_id,
            event_id=event_id,
            upload_error="אירעה שגיאה בשמירת הקובץ"
        ))

@app.route("/")
def home():
    return "HOME OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
