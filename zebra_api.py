import requests

ZEBRA_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

def update_askev_attendance(family_id, event_id, status, tickets, approval_date):
    ac_value = "אישרו" if status == "yes" else "ביטלו"
    arrive_qty = tickets if status == "yes" else 0

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
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
            <A_C>{ac_value}</A_C>
            <A_D>{approval_date}</A_D>
            <NO_ARIVE>{arrive_qty}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    headers = {"Content-Type": "application/xml; charset=utf-8"}
    response = requests.post(ZEBRA_URL, data=xml.encode("utf-8"), headers=headers, timeout=10)

    print("[ZEBRA REQUEST]")
    print(xml)
    print("[ZEBRA RESPONSE]")
    print(response.text)

    return response.text
