def get_event_data(event_id):
    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <ID_FILTER>{event_id}</ID_FILTER>

    <FIELDS>
        <EV_N/>
        <EV_D/>
        <EVE_HOUR/>
        <EVE_LOC/>
    </FIELDS>

    <CONNECTION_CARDS>
        <CONNECTION_CARD>
            <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

            <FIELDS>
                <ID/>
                <CO_NAME/>
            </FIELDS>

            <CON_FIELDS>
                <TOT_FFAM/>
                <PROV/>
            </CON_FIELDS>
        </CONNECTION_CARD>
    </CONNECTION_CARDS>
</ROOT>
"""

    headers = {"Content-Type": "application/xml"}
    response = requests.post(ZEBRA_URL, data=xml_body.encode("utf-8"), headers=headers)

    response_text = response.text.strip()

    # 🛡️ הגנה: אם זברה לא החזירה XML
    if not response_text.startswith("<"):
        print("===== RAW RESPONSE FROM ZEBRA =====")
        print(response_text)
        print("===== END RESPONSE =====")
        return None

    tree = ET.fromstring(response_text)

    card = tree.find(".//CARD")
    if card is None:
        return None

    event_data = {
        "event_name": card.findtext(".//EV_N", ""),
        "event_date": card.findtext(".//EV_D", ""),
        "event_time": card.findtext(".//EVE_HOUR", ""),
        "event_location": card.findtext(".//EVE_LOC", ""),
        "families": []
    }

    for conn in card.find("CONNECTIONS_CARDS"):
        fam_id = conn.findtext("ID")
        name = conn.findtext(".//CO_NAME")
        tickets = conn.findtext(".//TOT_FFAM")
        approved = conn.findtext(".//PROV")

        event_data["families"].append({
            "id": fam_id,
            "family_name": name,
            "tickets_approved": tickets,
            "approved": approved
        })

    return event_data
