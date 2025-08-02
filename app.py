from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
import os

# Inicijalizacija Flask aplikacije
app = Flask(__name__)
CORS(app)

# ➤ Konfiguracija iz environment varijabli (za sigurnost)
EMAIL_FROM = os.environ.get("EMAIL_FROM")  # npr. beautyrenea@gmail.com
EMAIL_PASS = os.environ.get("EMAIL_PASS")  # Gmail App Password (App Password, ne obična lozinka)
EMAIL_TO   = os.environ.get("EMAIL_TO")    # gdje šalješ obavijesti (isti ili drugi email)
MONGO_URI  = os.environ.get("MONGO_URI")  # tvoja MongoDB konekcija

# ➤ Konekcija na MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client["beauty"]
collection = db["rezervacije"]

# Test ruta
@app.route("/")
def home():
    return "💅 Beauty Studio Renea Backend radi!"

# Ping ruta (za npr. cron-job ping)
@app.route("/ping")
def ping():
    return "OK", 200

# Ruta za unos rezervacije
@app.route("/rezerviraj", methods=["POST"])
def rezerviraj():
    data = request.json
    if not data:
        return jsonify({"error": "Nema podataka"}), 400

    # Spremi u MongoDB
    collection.insert_one(data)

    # Pripremi email sadržaj
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

# Ruta za dohvat svih rezervacija (bez MongoDB _id polja)
@app.route("/rezervacije", methods=["GET"])
def get_rezervacije():
    rezervacije = list(collection.find({}, {"_id": 0}).sort("Termin"))
    return jsonify(rezervacije)

# Ruta za dohvat samo zauzetih termina (za frontend da zna koje termine blokirati)
@app.route("/api/zauzeti", methods=["GET"])
def zauzeti_termini():
    rezervacije = list(collection.find({}, {"_id": 0, "Termin": 1}))
    zauzeti = [r["Termin"] for r in rezervacije if "Termin" in r]
    return jsonify(zauzeti)

# Pokretanje Flask aplikacije lokalno
if __name__ == "__main__":
    try:
        client.admin.command("ping")
        print("✅ Spojeno na MongoDB!")
    except Exception as e:
        print("❌ Neuspješno spajanje na MongoDB:", e)
    app.run(debug=True)
