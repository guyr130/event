from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def home():
    return "המערכת פעילה ✔️"

@app.route("/confirm")
def confirm():
    # דוגמה — בהמשך יגיע מהזברה
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

@app.route("/thanks")
def thanks():
    status = request.args.get("s")  # yes / no
    qty = request.args.get("q")     # selected qty

    if status == "yes":
        message = f"אישורך נקלט 💙 (כמות שאושרה: {qty})"
    else:
        message = "העדכון נקלט 🧡"

    return render_template("thanks.html", message=message)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
