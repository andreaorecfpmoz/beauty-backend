from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
import os

# Inicijalizacija Flask aplikacije
app = Flask(__name__)
CORS(app)  # ✅ Dozvoli CORS

# ➤ Konfiguracija iz environment varijabli (preporučeno za sigurnost)
EMAIL_FROM = os.environ.get("EMAIL_FROM")  # npr. beautyrenea@gmail.com
EMAIL_PASS = os.environ.get("EMAIL_PASS")  # Gmail App Password
EMAIL_TO   = os.environ.get("EMAIL_TO")    # isti kao FROM ili neki drugi
MONGO_URI  = os.environ.get("MONGO_URI")

# ➤ Konekcija na MongoDB
client = MongoClient(MONGO_URI)
db = client["beauty"]
collection = db["rezervacije"]

# ✅ Test ruta
@app.route("/")
def home():
    return "💅 Beauty Studio Renea Backend radi!"

# ✅ Ruta za ping (za cron-job.org)
@app.route("/ping")
def ping():
    return "OK", 200

# ✅ Ruta za unos rezervacije
@app.route("/rezerviraj", methods=["POST"])
def rezerviraj():
    data = request.json
    if not data:
        return jsonify({"error": "Nema podataka"}), 400

    # Spremi u MongoDB
    collection.insert_one(data)

    # Pripremi sadržaj e-maila
    poruka = f"""
    📅 NOVA REZERVACIJA

    Ime i prezime: {data.get('Ime')}
    Broj telefona: {data.get('Broj')}
    Usluga: {data.get('Usluga')}
    Termin: {data.get('Termin')}
    """

    msg = MIMEText(poruka)
    msg["Subject"] = "💅 Nova rezervacija - Beauty Studio Renea"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("✅ E-mail poslan.")
    except Exception as e:
        print("❌ Greška pri slanju e-maila:", e)

    return jsonify({"message": "Rezervacija spremljena i e-mail poslan!"}), 201

# ✅ Ruta za dohvat svih rezervacija
@app.route("/rezervacije", methods=["GET"])
def get_rezervacije():
    rezervacije = list(collection.find({}, {"_id": 0}).sort("Termin"))
    return jsonify(rezervacije)

# ✅ Pokretanje aplikacije lokalno
if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("✅ Spojeno na MongoDB!")
    except Exception as e:
        print("❌ Neuspješno spajanje na MongoDB:", e)
    app.run(debug=True)
