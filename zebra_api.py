# -*- coding: utf-8 -*-
import requests
from datetime import datetime

# =========================
# Zebra API – Update Attendance
# =========================

ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


def update_zebra_attendance(
    family_id: int,
    event_id: int,
    status: str,   # "yes" / "no"
    qty: int
) -> bool:
    """
    Updates attendance data in Zebra CRM.
    """

    status_text = "אישרו" if status == "yes" else "ביטלו"
    today_str = datetime.now().strftime("%d/%m/%Y")

    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{family_id}</ID>
    </IDENTIFIER>

    <!-- חובה גם אם ריק -->
    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{status_text}</A_C>
            <A_D>{today_str}</A_D>
            <NO_ARIVE>{qty}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    headers = {
        "Content-Type": "application/xml"
    }

    try:
        response = requests.post(
            ZEBRA_UPDATE_URL,
            data=xml_body.encode("utf-8"),
            headers=headers,
            timeout=20
        )

        print("\n[ZEBRA] UPDATE REQUEST")
        print(xml_body)
        print("[ZEBRA] RESPONSE:")
        print(response.text)

        if "<code>0</code>" in response.text:
            print(
                f"[ZEBRA] UPDATE OK | family={family_id} | "
                f"event={event_id} | status={status_text} | qty={qty}"
            )
            return True
        else:
            print(
                f"[ZEBRA] UPDATE FAILED | family={family_id} | event={event_id}"
            )
            return False

    except Exception as e:
        print(
            f"[ZEBRA] EXCEPTION | family={family_id} | event={event_id} | {e}"
        )
        return False
