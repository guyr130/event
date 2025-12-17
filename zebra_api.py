# zebra_api.py
# -*- coding: utf-8 -*-

import requests
from datetime import datetime

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"


def update_askev_attendance(
    family_id: int,
    event_id: int,
    status_text: str,
    arrived_qty: int
):
    """
    עדכון אישור הגעה בכרטיס קשר ASKEV
    """

    today = datetime.now().strftime("%d/%m/%Y")

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

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{event_id}</VALUE>

        <FIELDS>
            <A_C>{status_text}</A_C>
            <A_D>{today}</A_D>
            <NO_ARIVE>{arrived_qty}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    headers = {
        "Content-Type": "application/xml; charset=utf-8"
    }

    response = requests.post(
        ZEBRA_URL,
        data=xml_body.encode("utf-8"),
        headers=headers,
        timeout=20
    )

    return response.status_code, response.text
