# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import base64

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# GOOGLE APPS SCRIPT
# ======================
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwWHwPHR8DMKAdm2oGx2m3OSW35KwDO3vBgFugxjkD70nbOZf0bjaAODWSNtRidICJT/exec"

# ======================
# FILE CONFIG
# ======================
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


def normalize_status(raw_status: str) -> str:
    value = str(raw_status or "").strip().lower()

    if value in ("yes", "approve", "approved", "1", "true"):
        return "yes"

    if value in ("no", "cancel", "cancelled", "canceled", "0", "false"):
        return "no"

    return ""


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def get_family_events(family_id: str):
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
            tickets = safe_int(tickets_raw, 0)

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
            return render_template(
                "confirm.html",
                family_id=family_id,
                family_name=family_name,
                event_id="",
                event_name="",
                event_date="",
                event_time="",
                location="",
                tickets=0,
                has_event=False
            )

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
                tickets=ev["tickets"],
                has_event=True
            )

        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name=family_name,
            events=valid_events
        )

    chosen = next((e for e in valid_events if str(e.get("event_id", "")).strip() == event_id), None)

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
            tickets=0,
            has_event=False
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
        tickets=chosen["tickets"],
        has_event=True
    )


# ======================
# UPLOAD FILE ONLY
# ======================
# ======================
# FAMILY EVENTS API
# ======================
@app.route("/api/family-events")
def api_family_events():
    family_id = (
        request.args.get("family_id") or ""
    ).strip()

    if not family_id:
        return jsonify({
            "success": False,
            "error": "Missing family_id"
        }), 400

    # בשלב הניסוי מאפשרים רק את משפחה 22442
    if family_id != "22442":
        return jsonify({
            "success": False,
            "error": "Family is not enabled for the pilot"
        }), 403

    family = get_family_events(family_id)

    if not family:
        return jsonify({
            "success": False,
            "error": "Family not found in Zebra"
        }), 404

    family_events = []

    for event in family.get("events", []):
        prov = str(
            event.get("prov", "")
        ).strip()

        family_events.append({
            "event_id": str(
                event.get("event_id", "")
            ).strip(),

            "event_name": str(
                event.get("event_name", "")
            ).strip(),

            "event_date": str(
                event.get("event_date", "")
            ).strip(),

            "event_time": str(
                event.get("event_time", "")
            ).strip(),

            "location": str(
                event.get("location", "")
            ).strip(),

            "tickets": safe_int(
                event.get("tickets", 0),
                0
            ),

            "prov": prov,

            "approved": (
                prov == "1"
            )
        })

    # מיון מהאירוע החדש לישן
    family_events.sort(
        key=lambda event:
            parse_ddmmyyyy(
                event.get("event_date", "")
            ) or datetime.min.date(),
        reverse=True
    )

    return jsonify({
        "success": True,
        "family": {
            "id": family_id,
            "name": family.get(
                "family_name",
                ""
            )
        },
        "events": family_events
    })
    # ======================
# FAMILY MEMBERS API
# ======================
@app.route("/api/family-members")
def api_family_members():
    family_id = (
        request.args.get("family_id") or ""
    ).strip()

    if not family_id or not family_id.isdigit():
        return jsonify({
            "success": False,
            "error": "Invalid family_id"
        }), 400

    # משפחות הניסוי בלבד
    if family_id not in {"22442", "21604"}:
        return jsonify({
            "success": False,
            "error": "Family is not enabled for the pilot"
        }), 403

    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{family_id}</ID_FILTER>

    <FIELDS>
        <CO_NAME></CO_NAME>
        <CP></CP>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>FAM</CONNECTION_KEY>

            <FIELDS>
                <ID></ID>
                <P_N></P_N>
                <F_N></F_N>
                <CELL></CELL>
                <TID></TID>
            </FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    try:
        response_text = zebra_post(xml_body)
        tree = ET.fromstring(response_text)

        card = tree.find(".//CARDS/CARD")

        if card is None:
            return jsonify({
                "success": False,
                "error": "Family not found in Zebra"
            }), 404

        family_name = (
            card.findtext(".//FIELDS/CO_NAME") or ""
        ).strip()

        cp_value = (
            card.findtext(".//FIELDS/CP") or ""
        ).strip()

        members = []

        connections = card.find(
            ".//CONNECTIONS_CARDS"
        )

        if connections is not None:
            for connection in list(connections):
                if not connection.tag.startswith(
                    "CARD_CONNECTION_"
                ):
                    continue

                member_id = (
                    connection.findtext("ID") or ""
                ).strip()

                first_name = (
                    connection.findtext(
                        ".//FIELDS/P_N"
                    ) or ""
                ).strip()

                last_name = (
                    connection.findtext(
                        ".//FIELDS/F_N"
                    ) or ""
                ).strip()

                phone = (
                    connection.findtext(
                        ".//FIELDS/CELL"
                    ) or ""
                ).strip()

                tid = (
                    connection.findtext(
                        ".//FIELDS/TID"
                    ) or ""
                ).strip()

                if not member_id:
                    continue

                members.append({
                    "member_id": member_id,
                    "first_name": first_name,
                    "last_name": last_name,

                    # מציגים רק 4 ספרות אחרונות
                    "phone_last4":
                        phone[-4:]
                        if len(phone) >= 4
                        else phone,

                    "tid_last4":
                        tid[-4:]
                        if len(tid) >= 4
                        else tid
                })

        members.sort(
            key=lambda member: (
                member.get("first_name", ""),
                member.get("last_name", "")
            )
        )

        return jsonify({
            "success": True,
            "family": {
                "id": family_id,
                "name": family_name,
                "cp": cp_value
            },
            "members": members
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500
@app.route("/upload_file", methods=["POST"])
def upload_file():
    family_id = str(request.form.get("family_id") or "").strip()
    uploaded_file = request.files.get("photo")

    if not family_id:
        return jsonify({"success": False, "error": "Missing family_id"}), 400

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "לא נבחר קובץ"}), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({
            "success": False,
            "error": "סוג קובץ לא נתמך. ניתן להעלות JPG / JPEG / PNG / WEBP / PDF בלבד."
        }), 400

    file_bytes = uploaded_file.read()
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "action": "upload_file",
        "family_id": family_id,
        "filename": uploaded_file.filename,
        "mime_type": uploaded_file.mimetype or "application/octet-stream",
        "file_base64": file_base64
    }

    print("UPLOAD_FILE -> sending to Apps Script")
    print("payload keys:", list(payload.keys()))
    print("family_id:", family_id)
    print("filename:", uploaded_file.filename)
    print("base64 length:", len(file_base64))

    try:
        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=60
        )

        print("UPLOAD_FILE -> Apps Script status:", r.status_code)
        print("UPLOAD_FILE -> Apps Script body:", (r.text or "")[:1000])

        data = r.json()

        is_ok = bool(data.get("success")) or bool(data.get("ok"))

        if not is_ok:
            return jsonify({
                "success": False,
                "error": data.get("error", "שגיאה בהעלאה")
            }), 500

        return jsonify({
            "success": True,
            "filename": data.get("saved_as") or data.get("filename", ""),
            "total_uploads": data.get("total_uploads", ""),
            "folder_url": data.get("folder_url", "")
        })

    except Exception as e:
        print("UPLOAD_FILE ERROR:", str(e))
        return jsonify({
            "success": False,
            "error": f"שגיאה בהעלאה: {str(e)}"
        }), 500


# ======================
# SUBMIT
# ======================
@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}

    event_id = str(data.get("event_id") or "").strip()
    family_id = str(data.get("family_id") or "").strip()
    status = normalize_status(data.get("status"))
    tickets = safe_int(data.get("tickets", 0), 0)

    family_name = str(data.get("family_name") or "").strip()
    event_name = str(data.get("event_name") or "").strip()
    transport = str(data.get("transport") or "").strip()

    if not event_id or not family_id or status not in ("yes", "no"):
        return jsonify({"success": False, "error": "Missing or invalid parameters"}), 400

    if status == "no":
        tickets = 0
        transport = ""

    if is_duplicate(event_id, family_id, status, tickets):
        return jsonify({"success": True, "duplicate": True})

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    status_he = "אישרו" if status == "yes" else "ביטלו"

    payload = {
        "timestamp": timestamp,
        "family_id": family_id,
        "family_name": family_name,
        "event_id": event_id,
        "event_name": event_name,
        "status": status_he,
        "tickets": tickets,
        "transport": transport
    }

    try:
        print("TRANSPORT =", transport)
        print("PAYLOAD =", payload)

        r = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=20
        )
        
        return jsonify({
            "success": True,
            "google_status": r.status_code,
            "google_body": (r.text or "")[:400],
            "status": status,
            "tickets": tickets,
            "transport": transport
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = normalize_status(request.args.get("status", ""))
    qty = request.args.get("qty", "0")
    event_id = request.args.get("event_id", "")
    family_id = request.args.get("family_id", "")
    transport = request.args.get("transport", "")

    return render_template(
        "thanks.html",
        status=status,
        qty=qty,
        event_id=event_id,
        family_id=family_id,
        transport=transport
    )

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "Server is alive"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
