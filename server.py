from flask import Flask, render_template, request

app = Flask(__name__)

# -----------------------------------------------------
# דף הבית — מפנה אוטומטית ל /confirm
# -----------------------------------------------------
@app.route("/")
def home():
    return """
    <script>
        window.location.href = "/confirm";
    </script>
    """

# -----------------------------------------------------
# דף האישור הראשי (Confirm)
# -----------------------------------------------------
@app.route("/confirm")
def confirm():
    # נתונים לדוגמה – בהמשך ישלפו מהזברה
    family_name = "רייטר"
    tickets = 5
    event_name = "אירוע חנוכה"
    event_date = "18.12"
    event_time = "19:00"
    location = "תל אביב"

    return render_template(
        "confirm.html",
        family_name=family_name,
        tickets=tickets,
        event_name=event_name,
        event_date=event_date,
        event_time=event_time,
        location=location
    )

# -----------------------------------------------------
# דף הת THANKS (הודעה לאחר לחיצה)
# -----------------------------------------------------
@app.route("/thanks")
def thanks():
    status = request.args.get("s")  # yes / no
    qty = request.args.get("q")     # כמות שנבחרה

    return render_template("thanks.html", status=status, qty=qty)

# -----------------------------------------------------
# הרצת השרת
# -----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
