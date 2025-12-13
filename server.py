from flask import Flask, render_template, request

app = Flask(__name__)

# עמוד אישור ההגעה (טופס)
@app.route("/", methods=["GET"])
def confirm_page():
    return render_template("confirm.html")

# כאשר המשתמש מאשר או לא מאשר
@app.route("/submit", methods=["POST"])
def submit():
    attending = request.form.get("attending")
    tickets = request.form.get("tickets")

    return render_template("thanks.html", attending=attending, tickets=tickets)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
