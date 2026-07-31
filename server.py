# -*- coding: utf-8 -*-
from flask import Flask, request, render_template, jsonify
import base64
from datetime import datetime, timedelta
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = (
    "https://25098.zebracrm.com/"
    "ext_interface.php?b=get_multi_cards_details"
)
ZEBRA_UPDATE_URL = (
    "https://25098.zebracrm.com/"
    "ext_interface.php?b=update_customer"
)
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

# ======================
# GOOGLE APPS SCRIPT
# ======================
GOOGLE_SHEETS_WEBAPP_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbwWHwPHR8DMKAdm2oGx2m3OSW35KwDO3vBgFugxjkD70nbOZf0bjaAODWSNtRidICJT/"
    "exec"
)

# ======================
# PILOT FAMILIES
# ======================
PILOT_FAMILY_IDS = {
    "22442",
    "21604",
    "21774"
}

# ======================
# FILE CONFIG
# ======================
ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf"
}

# ======================
# IDEMPOTENCY
# ======================
recent_requests = {}
IDEMPOTENCY_WINDOW = 15


def is_duplicate(
    event_id,
    family_id,
    status,
    tickets
):
    now = time.time()

    key = (
        f"{event_id}|"
        f"{family_id}|"
        f"{status}|"
        f"{tickets}"
    )

    expired = [
        item_key
        for item_key, created_at
        in recent_requests.items()
        if now - created_at >
        IDEMPOTENCY_WINDOW
    ]

    for item_key in expired:
        del recent_requests[item_key]

    if key in recent_requests:
        return True

    recent_requests[key] = now
    return False


def zebra_post(
    xml_body: str,
    timeout: int = 15
) -> str:
    response = requests.post(
        ZEBRA_GET_URL,
        data=xml_body.encode("utf-8"),
        headers={
            "Content-Type":
                "application/xml"
        },
        timeout=timeout
    )

    return response.text


def parse_ddmmyyyy(
    date_str: str
):
    value = (
        date_str or ""
    ).strip()

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%d/%m/%Y"
        ).date()

    except Exception:
        return None


def allowed_file(
    filename: str
) -> bool:
    if (
        not filename or
        "." not in filename
    ):
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return (
        extension in
        ALLOWED_EXTENSIONS
    )


def normalize_status(
    raw_status: str
) -> str:
    value = str(
        raw_status or ""
    ).strip().lower()

    if value in (
        "yes",
        "approve",
        "approved",
        "1",
        "true"
    ):
        return "yes"

    if value in (
        "no",
        "cancel",
        "cancelled",
        "canceled",
        "0",
        "false"
    ):
        return "no"

    return ""


def safe_int(
    value,
    default=0
):
    try:
        return int(value)

    except Exception:
        return default


def escape_xml(
    value
) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def normalize_israeli_id(
    value
) -> str:
    digits = "".join(
        character
        for character in str(value or "")
        if character.isdigit()
    )

    if (
        not digits or
        len(digits) > 9
    ):
        return ""

    return digits.zfill(9)


def is_valid_israeli_id(
    value
) -> bool:
    identity_number = normalize_israeli_id(
        value
    )

    if len(identity_number) != 9:
        return False

    if identity_number == "000000000":
        return False

    total = 0

    for index, character in enumerate(
        identity_number
    ):
        number = int(character)
        product = number * (
            1 if index % 2 == 0 else 2
        )

        total += (
            product
            if product < 10
            else product - 9
        )

    return total % 10 == 0


def get_family_member_records(
    family_id: str
):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{escape_xml(ZEBRA_USER)}</USERNAME>
        <PASSWORD>{escape_xml(ZEBRA_PASS)}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>business_customer</CARD_TYPE_FILTER>
    <ID_FILTER>{escape_xml(family_id)}</ID_FILTER>

    <FIELDS>
        <CO_NAME></CO_NAME>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>FAM</CONNECTION_KEY>
            <FIELDS>
                <ID></ID>
                <TID></TID>
            </FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    response_text = zebra_post(
        xml_body
    )

    tree = ET.fromstring(
        response_text
    )

    card = tree.find(
        ".//CARDS/CARD"
    )

    if card is None:
        return None

    members = {}
    connections = card.find(
        ".//CONNECTIONS_CARDS"
    )

    if connections is not None:
        for connection in list(
            connections
        ):
            if not connection.tag.startswith(
                "CARD_CONNECTION_"
            ):
                continue

            member_id = (
                connection.findtext("ID")
                or ""
            ).strip()

            tid = (
                connection.findtext(
                    ".//FIELDS/TID"
                ) or ""
            ).strip()

            if member_id:
                members[member_id] = {
                    "tid": tid
                }

    return members


def update_member_tid_in_zebra(
    member_id: str,
    identity_number: str
):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{escape_xml(ZEBRA_USER)}</USERNAME>
        <PASSWORD>{escape_xml(ZEBRA_PASS)}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{escape_xml(member_id)}</ID>
    </IDENTIFIER>

    <CUST_DETAILS>
        <TID>{escape_xml(identity_number)}</TID>
    </CUST_DETAILS>
</ROOT>
""".strip()

    response = requests.post(
        ZEBRA_UPDATE_URL,
        data=xml_body.encode("utf-8"),
        headers={
            "Content-Type":
                "application/xml"
        },
        timeout=15
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Zebra update failed with HTTP "
            f"{response.status_code}"
        )

    response_text = response.text or ""

    try:
        tree = ET.fromstring(
            response_text
        )

        message = (
            tree.findtext(".//msg")
            or ""
        ).strip().lower()

        if "error" in message or "fail" in message:
            raise RuntimeError(
                "Zebra rejected the identity update"
            )

    except ET.ParseError:
        pass


def event_datetime_in_israel(
    event_date: str,
    event_time: str
):
    date_value = str(
        event_date or ""
    ).strip()

    time_value = str(
        event_time or ""
    ).strip()[:5]

    if (
        not date_value or
        not time_value
    ):
        return None

    try:
        return datetime.strptime(
            f"{date_value} {time_value}",
            "%d/%m/%Y %H:%M"
        ).replace(
            tzinfo=ZoneInfo(
                "Asia/Jerusalem"
            )
        )

    except ValueError:
        return None


def cancel_family_event_in_zebra(
    family_id: str,
    event_id: str
):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{escape_xml(ZEBRA_USER)}</USERNAME>
        <PASSWORD>{escape_xml(ZEBRA_PASS)}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{escape_xml(family_id)}</ID>
    </IDENTIFIER>

    <CONNECTION_CARD_DETAILS>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{escape_xml(event_id)}</VALUE>

        <FIELDS>
            <TIC_A>0</TIC_A>
            <ADDI_INV>0</ADDI_INV>
            <CANCEL_AT>1</CANCEL_AT>
            <PROV>0</PROV>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
""".strip()

    response = requests.post(
        ZEBRA_UPDATE_URL,
        data=xml_body.encode("utf-8"),
        headers={
            "Content-Type":
                "application/xml"
        },
        timeout=15
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Zebra cancellation failed with HTTP "
            f"{response.status_code}"
        )

    response_text = response.text or ""

    try:
        tree = ET.fromstring(
            response_text
        )

        message = (
            tree.findtext(".//msg")
            or ""
        ).strip().lower()

        if (
            "error" in message or
            "fail" in message
        ):
            raise RuntimeError(
                "Zebra rejected the cancellation"
            )

    except ET.ParseError:
        pass


# ======================
# FAMILY EVENTS FROM ZEBRA
# ======================
def get_family_events(
    family_id: str
):
    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>business_customer</CARD_TYPE_FILTER>
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
                <FULL_N></FULL_N>
                <CANCEL_AT></CANCEL_AT>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
""".strip()

    response_text = zebra_post(
        xml_body
    )

    tree = ET.fromstring(
        response_text
    )

    card = tree.find(
        ".//CARDS/CARD"
    )

    if card is None:
        return None

    family_name = (
        card.findtext(
            ".//FIELDS/CO_NAME"
        ) or ""
    ).strip()

    events = []

    connections = card.find(
        ".//CONNECTIONS_CARDS"
    )

    if connections is not None:
        for connection in list(
            connections
        ):
            if not connection.tag.startswith(
                "CARD_CONNECTION_"
            ):
                continue

            event_id = (
                connection.findtext(
                    "ID"
                ) or ""
            ).strip()

            event_name = (
                connection.findtext(
                    ".//FIELDS/EV_N"
                ) or ""
            ).strip()

            event_date = (
                connection.findtext(
                    ".//FIELDS/EV_D"
                ) or ""
            ).strip()

            event_time = (
                connection.findtext(
                    ".//FIELDS/EVE_HOUR"
                ) or ""
            ).strip()

            location = (
                connection.findtext(
                    ".//FIELDS/EVE_LOC"
                ) or ""
            ).strip()

            tickets_raw = (
                connection.findtext(
                    ".//CON_FIELDS/TOT_FFAM"
                ) or "0"
            ).strip()

            tickets = safe_int(
                tickets_raw,
                0
            )

            prov = (
                connection.findtext(
                    ".//CON_FIELDS/PROV"
                ) or ""
            ).strip()

            inviter_name = (
                connection.findtext(
                    ".//CON_FIELDS/FULL_N"
                ) or ""
            ).strip()

            cancel_at = (
                connection.findtext(
                    ".//CON_FIELDS/CANCEL_AT"
                ) or ""
            ).strip()

            events.append({
                "event_id":
                    event_id,

                "event_name":
                    event_name,

                "event_date":
                    event_date,

                "event_time":
                    event_time,

                "location":
                    location,

                "tickets":
                    tickets,

                "prov":
                    prov,

                "inviter_name":
                    inviter_name,

                "cancelled": (
                    cancel_at == "1"
                )
            })

    return {
        "family_id":
            family_id,

        "family_name":
            family_name,

        "events":
            events
    }


def filter_events(
    events
):
    today = datetime.today().date()
    valid = []

    for event in events:
        prov = str(
            event.get(
                "prov",
                ""
            )
        ).strip()

        if prov != "1":
            continue

        event_date = parse_ddmmyyyy(
            event.get(
                "event_date",
                ""
            )
        )

        if not event_date:
            continue

        if event_date < today:
            continue

        valid.append(
            event
        )

    valid.sort(
        key=lambda event: (
            parse_ddmmyyyy(
                event.get(
                    "event_date",
                    ""
                )
            ) or today,

            (
                event.get(
                    "event_time"
                ) or "00:00"
            ).strip()
        )
    )

    return valid


# ======================
# CONFIRM
# ======================
@app.route("/confirm")
def confirm():
    family_id = (
        request.args.get(
            "family_id"
        ) or ""
    ).strip()

    event_id = (
        request.args.get(
            "event_id"
        ) or ""
    ).strip()

    if not family_id:
        return (
            "Missing family_id",
            400
        )

    family = get_family_events(
        family_id
    )

    if not family:
        return (
            "Family not found in Zebra",
            404
        )

    family_name = family[
        "family_name"
    ]

    valid_events = filter_events(
        family["events"]
    )

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
            event = valid_events[0]

            return render_template(
                "confirm.html",
                family_id=family_id,
                family_name=family_name,
                event_id=event[
                    "event_id"
                ],
                event_name=event[
                    "event_name"
                ],
                event_date=event[
                    "event_date"
                ],
                event_time=event[
                    "event_time"
                ],
                location=event[
                    "location"
                ],
                tickets=event[
                    "tickets"
                ],
                has_event=True
            )

        return render_template(
            "select_event.html",
            family_id=family_id,
            family_name=family_name,
            events=valid_events
        )

    chosen = next(
        (
            event
            for event in valid_events
            if str(
                event.get(
                    "event_id",
                    ""
                )
            ).strip() == event_id
        ),
        None
    )

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
        event_id=chosen[
            "event_id"
        ],
        event_name=chosen[
            "event_name"
        ],
        event_date=chosen[
            "event_date"
        ],
        event_time=chosen[
            "event_time"
        ],
        location=chosen[
            "location"
        ],
        tickets=chosen[
            "tickets"
        ],
        has_event=True
    )


# ======================
# FAMILY EVENTS API
# ======================
@app.route("/api/family-events")
def api_family_events():
    family_id = (
        request.args.get(
            "family_id"
        ) or ""
    ).strip()

    if (
        not family_id or
        not family_id.isdigit()
    ):
        return jsonify({
            "success": False,
            "error":
                "Invalid family_id"
        }), 400

    if (
        family_id not in
        PILOT_FAMILY_IDS
    ):
        return jsonify({
            "success": False,
            "error":
                "Family is not enabled for the pilot"
        }), 403

    family = get_family_events(
        family_id
    )

    if not family:
        return jsonify({
            "success": False,
            "error":
                "Family not found in Zebra"
        }), 404

    family_events = []

    for event in family.get(
        "events",
        []
    ):
        prov = str(
            event.get(
                "prov",
                ""
            )
        ).strip()

        family_events.append({
            "event_id": str(
                event.get(
                    "event_id",
                    ""
                )
            ).strip(),

            "event_name": str(
                event.get(
                    "event_name",
                    ""
                )
            ).strip(),

            "event_date": str(
                event.get(
                    "event_date",
                    ""
                )
            ).strip(),

            "event_time": str(
                event.get(
                    "event_time",
                    ""
                )
            ).strip(),

            "location": str(
                event.get(
                    "location",
                    ""
                )
            ).strip(),

            "tickets": safe_int(
                event.get(
                    "tickets",
                    0
                ),
                0
            ),

            "prov":
                prov,

            "approved": (
                prov == "1"
            ),

            "inviter_name": str(
                event.get(
                    "inviter_name",
                    ""
                )
            ).strip(),

            "cancelled": bool(
                event.get(
                    "cancelled",
                    False
                )
            )
        })

    family_events.sort(
        key=lambda event:
            parse_ddmmyyyy(
                event.get(
                    "event_date",
                    ""
                )
            ) or datetime.min.date(),
        reverse=True
    )

    return jsonify({
        "success": True,

        "family": {
            "id":
                family_id,

            "name":
                family.get(
                    "family_name",
                    ""
                )
        },

        "events":
            family_events
    })


# ======================
# CANCEL FAMILY EVENT API
# ======================
@app.route(
    "/api/cancel-family-event",
    methods=["POST"]
)
def api_cancel_family_event():
    data = (
        request.get_json(
            silent=True
        ) or {}
    )

    family_id = str(
        data.get("family_id") or ""
    ).strip()

    event_id = str(
        data.get("event_id") or ""
    ).strip()

    if (
        not family_id.isdigit() or
        not event_id.isdigit()
    ):
        return jsonify({
            "success": False,
            "error":
                "Invalid family or event"
        }), 400

    if family_id not in PILOT_FAMILY_IDS:
        return jsonify({
            "success": False,
            "error":
                "Family is not enabled for the pilot"
        }), 403

    try:
        family = get_family_events(
            family_id
        )

        if not family:
            return jsonify({
                "success": False,
                "error":
                    "Family not found in Zebra"
            }), 404

        family_event = next(
            (
                event
                for event in family.get(
                    "events",
                    []
                )
                if str(
                    event.get(
                        "event_id",
                        ""
                    )
                ).strip() == event_id
            ),
            None
        )

        if not family_event:
            return jsonify({
                "success": False,
                "error":
                    "Registration not found"
            }), 404

        if bool(
            family_event.get(
                "cancelled",
                False
            )
        ):
            return jsonify({
                "success": True,
                "already_cancelled": True
            })

        tickets = safe_int(
            family_event.get(
                "tickets",
                0
            ),
            0
        )

        approved = str(
            family_event.get(
                "prov",
                ""
            )
        ).strip() == "1"

        if tickets <= 0 and not approved:
            return jsonify({
                "success": False,
                "error":
                    "Registration not found"
            }), 404

        event_datetime = event_datetime_in_israel(
            family_event.get(
                "event_date",
                ""
            ),
            family_event.get(
                "event_time",
                ""
            )
        )

        if event_datetime is None:
            return jsonify({
                "success": False,
                "error":
                    "לא ניתן לחשב את מועד הביטול לאירוע זה"
            }), 409

        cancellation_deadline = (
            event_datetime -
            timedelta(hours=24)
        )

        now = datetime.now(
            ZoneInfo(
                "Asia/Jerusalem"
            )
        )

        if now >= cancellation_deadline:
            return jsonify({
                "success": False,
                "error":
                    "מועד הביטול לאירוע זה הסתיים"
            }), 409

        cancel_family_event_in_zebra(
            family_id,
            event_id
        )

        return jsonify({
            "success": True,
            "event_id": event_id,
            "cancellation_sent": True,
            "cancelled_at":
                now.isoformat(),
            "cancellation_deadline":
                cancellation_deadline.isoformat()
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error":
                str(error)
        }), 500


# ======================
# FAMILY MEMBERS API
# ======================
@app.route("/api/family-members")
def api_family_members():
    family_id = (
        request.args.get(
            "family_id"
        ) or ""
    ).strip()

    if (
        not family_id or
        not family_id.isdigit()
    ):
        return jsonify({
            "success": False,
            "error":
                "Invalid family_id"
        }), 400

    if (
        family_id not in
        PILOT_FAMILY_IDS
    ):
        return jsonify({
            "success": False,
            "error":
                "Family is not enabled for the pilot"
        }), 403

    xml_body = f"""
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>business_customer</CARD_TYPE_FILTER>
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
        response_text = zebra_post(
            xml_body
        )

        tree = ET.fromstring(
            response_text
        )

        card = tree.find(
            ".//CARDS/CARD"
        )

        if card is None:
            return jsonify({
                "success": False,
                "error":
                    "Family not found in Zebra"
            }), 404

        family_name = (
            card.findtext(
                ".//FIELDS/CO_NAME"
            ) or ""
        ).strip()

        cp_value = (
            card.findtext(
                ".//FIELDS/CP"
            ) or ""
        ).strip()

        members = []

        connections = card.find(
            ".//CONNECTIONS_CARDS"
        )

        if connections is not None:
            for connection in list(
                connections
            ):
                if not connection.tag.startswith(
                    "CARD_CONNECTION_"
                ):
                    continue

                member_id = (
                    connection.findtext(
                        "ID"
                    ) or ""
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

                tid_digits = "".join(
                    character
                    for character in tid
                    if character.isdigit()
                )

                tid_length = len(
                    tid_digits
                )

                missing_leading_zeros = (
                    9 - tid_length
                    if 6 <= tid_length < 9
                    else 0
                )

                padded_tid = (
                    tid_digits.zfill(9)
                    if missing_leading_zeros > 0
                    else ""
                )

                can_complete_with_zeros = (
                    bool(padded_tid) and
                    is_valid_israeli_id(
                        padded_tid
                    )
                )

                members.append({
                    "member_id":
                        member_id,

                    "first_name":
                        first_name,

                    "last_name":
                        last_name,

                    "phone_last4":
                        phone[-4:]
                        if len(phone) >= 4
                        else phone,

                    "tid_last4":
                        tid[-4:]
                        if len(tid) >= 4
                        else tid,

                    "tid_length":
                        tid_length,

                    "missing_leading_zeros": (
                        missing_leading_zeros
                        if can_complete_with_zeros
                        else 0
                    ),

                    "can_complete_with_zeros":
                        can_complete_with_zeros
                })

        members.sort(
            key=lambda member: (
                member.get(
                    "first_name",
                    ""
                ),
                member.get(
                    "last_name",
                    ""
                )
            )
        )

        return jsonify({
            "success": True,

            "family": {
                "id":
                    family_id,

                "name":
                    family_name,

                "cp":
                    cp_value
            },

            "members":
                members
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error":
                str(error)
        }), 500


# ======================
# UPDATE FAMILY MEMBER ID
# ======================
@app.route(
    "/api/update-family-member-id",
    methods=["POST"]
)
def api_update_family_member_id():
    data = (
        request.get_json(
            silent=True
        ) or {}
    )

    family_id = str(
        data.get("family_id") or ""
    ).strip()

    member_id = str(
        data.get("member_id") or ""
    ).strip()

    add_missing_leading_zeros = bool(
        data.get(
            "add_missing_leading_zeros"
        )
    )

    identity_number = ""

    if not add_missing_leading_zeros:
        identity_number = normalize_israeli_id(
            data.get("identity_number")
        )

    if (
        not family_id.isdigit() or
        not member_id.isdigit()
    ):
        return jsonify({
            "success": False,
            "error":
                "Invalid family or member"
        }), 400

    if family_id not in PILOT_FAMILY_IDS:
        return jsonify({
            "success": False,
            "error":
                "Family is not enabled for the pilot"
        }), 403

    if (
        not add_missing_leading_zeros and
        not is_valid_israeli_id(
            identity_number
        )
    ):
        return jsonify({
            "success": False,
            "error":
                "מספר תעודת הזהות אינו תקין"
        }), 400

    try:
        member_records = get_family_member_records(
            family_id
        )

        if member_records is None:
            return jsonify({
                "success": False,
                "error":
                    "Family not found in Zebra"
            }), 404

        if member_id not in member_records:
            return jsonify({
                "success": False,
                "error":
                    "האדם שנבחר אינו שייך למשפחה"
            }), 403

        if add_missing_leading_zeros:
            stored_tid = str(
                member_records[member_id].get(
                    "tid",
                    ""
                ) or ""
            ).strip()

            stored_digits = "".join(
                character
                for character in stored_tid
                if character.isdigit()
            )

            if not 6 <= len(stored_digits) < 9:
                return jsonify({
                    "success": False,
                    "error":
                        "לא ניתן להשלים אפסים למספר השמור"
                }), 400

            identity_number = stored_digits.zfill(9)

            if not is_valid_israeli_id(
                identity_number
            ):
                return jsonify({
                    "success": False,
                    "error":
                        "הוספת אפסים אינה יוצרת תעודת זהות תקינה"
                }), 400

        update_member_tid_in_zebra(
            member_id,
            identity_number
        )

        return jsonify({
            "success": True,
            "member_id":
                member_id,
            "tid_last4":
                identity_number[-4:],
            "tid_length":
                9
        }), 200

    except Exception as error:
        return jsonify({
            "success": False,
            "error":
                str(error)
        }), 502


# ======================
# UPLOAD FILE
# ======================
@app.route(
    "/upload_file",
    methods=["POST"]
)
def upload_file():
    family_id = str(
        request.form.get(
            "family_id"
        ) or ""
    ).strip()

    uploaded_file = request.files.get(
        "photo"
    )

    if not family_id:
        return jsonify({
            "success": False,
            "error":
                "Missing family_id"
        }), 400

    if (
        not uploaded_file or
        not uploaded_file.filename
    ):
        return jsonify({
            "success": False,
            "error":
                "לא נבחר קובץ"
        }), 400

    if not allowed_file(
        uploaded_file.filename
    ):
        return jsonify({
            "success": False,
            "error":
                "סוג קובץ לא נתמך. "
                "ניתן להעלות JPG / JPEG / "
                "PNG / WEBP / PDF בלבד."
        }), 400

    file_bytes = (
        uploaded_file.read()
    )

    file_base64 = (
        base64
        .b64encode(file_bytes)
        .decode("utf-8")
    )

    payload = {
        "action":
            "upload_file",

        "family_id":
            family_id,

        "filename":
            uploaded_file.filename,

        "mime_type":
            uploaded_file.mimetype
            or "application/octet-stream",

        "file_base64":
            file_base64
    }

    try:
        response = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=60
        )

        data = response.json()

        is_ok = (
            bool(data.get("success")) or
            bool(data.get("ok"))
        )

        if not is_ok:
            return jsonify({
                "success": False,
                "error":
                    data.get(
                        "error",
                        "שגיאה בהעלאה"
                    )
            }), 500

        return jsonify({
            "success": True,

            "filename":
                data.get(
                    "saved_as"
                )
                or data.get(
                    "filename",
                    ""
                ),

            "total_uploads":
                data.get(
                    "total_uploads",
                    ""
                ),

            "folder_url":
                data.get(
                    "folder_url",
                    ""
                )
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error":
                f"שגיאה בהעלאה: {error}"
        }), 500


# ======================
# SUBMIT
# ======================
@app.route(
    "/submit",
    methods=["POST"]
)
def submit():
    data = (
        request.get_json(
            silent=True
        ) or {}
    )

    event_id = str(
        data.get(
            "event_id"
        ) or ""
    ).strip()

    family_id = str(
        data.get(
            "family_id"
        ) or ""
    ).strip()

    status = normalize_status(
        data.get(
            "status"
        )
    )

    tickets = safe_int(
        data.get(
            "tickets",
            0
        ),
        0
    )

    family_name = str(
        data.get(
            "family_name"
        ) or ""
    ).strip()

    event_name = str(
        data.get(
            "event_name"
        ) or ""
    ).strip()

    transport = str(
        data.get(
            "transport"
        ) or ""
    ).strip()

    if (
        not event_id or
        not family_id or
        status not in (
            "yes",
            "no"
        )
    ):
        return jsonify({
            "success": False,
            "error":
                "Missing or invalid parameters"
        }), 400

    if status == "no":
        tickets = 0
        transport = ""

    if is_duplicate(
        event_id,
        family_id,
        status,
        tickets
    ):
        return jsonify({
            "success": True,
            "duplicate": True
        })

    timestamp = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    status_he = (
        "אישרו"
        if status == "yes"
        else "ביטלו"
    )

    payload = {
        "timestamp":
            timestamp,

        "family_id":
            family_id,

        "family_name":
            family_name,

        "event_id":
            event_id,

        "event_name":
            event_name,

        "status":
            status_he,

        "tickets":
            tickets,

        "transport":
            transport
    }

    try:
        response = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=payload,
            timeout=20
        )

        return jsonify({
            "success": True,

            "google_status":
                response.status_code,

            "google_body":
                (
                    response.text or ""
                )[:400],

            "status":
                status,

            "tickets":
                tickets,

            "transport":
                transport
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error":
                str(error)
        }), 500


# ======================
# THANKS
# ======================
@app.route("/thanks")
def thanks():
    status = normalize_status(
        request.args.get(
            "status",
            ""
        )
    )

    qty = request.args.get(
        "qty",
        "0"
    )

    event_id = request.args.get(
        "event_id",
        ""
    )

    family_id = request.args.get(
        "family_id",
        ""
    )

    transport = request.args.get(
        "transport",
        ""
    )

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
    app.run(
        host="0.0.0.0",
        port=10000,
        debug=True
    )
