from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

ZEBRA_UPDATE_URL = "https://25098.zebracrm.com/ext_interface.php?b=update_customer"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"

FIXED_DATE = "18/12/2025"

@app.route("/")
def home():
    return """
    <html lang="he" dir="rtl">
    <body style="font-family:Arial;text-align:center;margin-top:50px">
        <h2>בדיקת Zebra API</h2>

        <button onclick="send('yes',2)">מגיעים (2)</button>
        <br><br>
        <button onclick="send('no',0)">לא מגיעים</button>

        <script>
        function send(status, qty) {
            fetch('/test', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    family_id: 22055,
                    event_id: 22354,
                    status: status,
                    tickets: qty
                })
            })
            .then(r => r.text())
            .then(t => alert(t));
        }
        </script>
    </body>
    </html>
    """

@app.route("/test", methods=["POST"])
def test():
    data = request.json

    zebra_status = "אישרו" if data["status"] == "yes" else "ביטלו"
    zebra_tickets = data["tickets"] if data["status"] == "yes" else 0

    zebra_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE>business_customer</CARD_TYPE>

    <IDENTIFIER>
        <ID>{data["family_id"]}</ID>
    </IDENTIFIER>

    <CUST_DETAILS></CUST_DETAILS>

    <CONNECTION_CARD_DETAILS>
        <UPDATE_EVEN_CONNECTED>1</UPDATE_EVEN_CONNECTED>
        <CONNECTION_KEY>ASKEV</CONNECTION_KEY>
        <KEY>ID</KEY>
        <VALUE>{data["event_id"]}</VALUE>

        <FIELDS>
            <A_C>{zebra_status}</A_C>
            <A_D>{FIXED_DATE}</A_D>
            <NO_ARIVE>{zebra_tickets}</NO_ARIVE>
        </FIELDS>
    </CONNECTION_CARD_DETAILS>
</ROOT>
"""

    r = requests.post(
        ZEBRA_UPDATE_URL,
        data=zebra_xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=10
    )

    return f"Zebra response:\n{r.text}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
