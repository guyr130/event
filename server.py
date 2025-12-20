    # ======================
    # 2️⃣ ZEBRA UPDATE (SAFE – לא שובר כלום)
    # ======================
    try:
        zebra_status = "אישרו" if status == "yes" else "ביטלו"
        zebra_tickets = tickets if status == "yes" else 0

        zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
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
            <A_C>{zebra_status}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

        zr = requests.post(
            ZEBRA_UPDATE_URL,
            data=zebra_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=10
        )

        print("Zebra status:", zr.status_code)
        print("Zebra response:", zr.text)

    except Exception as e:
        # ❗ קריטי – לא זורקים חריגה
        print("Zebra FAILED but flow continues:", e)
