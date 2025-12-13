def get_event_data(event_id):
    xml_body = f"""
    <ROOT>
        <PERMISSION>
            <USERNAME>{ZEBRA_USER}</USERNAME>
            <PASSWORD>{ZEBRA_PASS}</PASSWORD>
        </PERMISSION>

        <ID_FILTER>{event_id}</ID_FILTER>

        <FIELDS>
            <EV_N></EV_N>
            <EV_D></EV_D>
            <EVE_HOUR></EVE_HOUR>
            <EVE_LOC></EVE_LOC>
        </FIELDS>

        <CONNECTION_CARDS>
            <CONNECTION_CARD>
                <CONNECTION_KEY>ASKEV</CONNECTION_KEY>

                <FIELDS>
                    <ID></ID>
                    <CO_NAME></CO_NAME>
                </FIELDS>

                <CON_FIELDS>
                    <TOT_FFAM></TOT_FFAM>
                    <PROV></PROV>
                </CON_FIELDS>
            </CONNECTION_CARD>
        </CONNECTION_CARDS>
    </ROOT>
    """

    headers = {"Content-Type": "application/xml"}
    response = requests.post(ZEBRA_URL, data=xml_body.encode("utf-8"), headers=headers)

    raw = response.text.strip()

    print("===== RAW XML FROM ZEBRA =====")
    print(raw)
    print("===== END RAW XML =====")

    if not raw.startswith("<"):
        return None  # קיבלנו שגיאה במקום XML

    tree = ET.fromstring(raw)
    card = tree.find(".//CARD")
    if card is None:
        return None

    event_data = {
        "event_name": card.findtext(".//EV_N", default=""),
        "event_date": card.findtext(".//EV_D", default=""),
        "event_time": card.findtext(".//EVE_HOUR", default=""),
        "event_location": card.findtext(".//EVE_LOC", default=""),
        "families": []
    }

    for f in card.findall(".//CONNECTIONS_CARDS/*"):
        fam_id = f.findtext("ID")
        name = f.findtext(".//CO_NAME")
        tickets = f.findtext(".//TOT_FFAM")
        approved = f.findtext(".//PROV")

        event_data["families"].append({
            "id": fam_id,
            "family_name": name,
            "tickets_approved": tickets,
            "approved": approved
        })

    return event_data
