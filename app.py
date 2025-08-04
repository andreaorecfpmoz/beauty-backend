from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime, timedelta

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

def formatiraj_termin(termin_str):
    """Vrati termin kao '05.08.2025. u 09:30' ili originalni string ako ne može parsirati"""
    try:
        termin_dt = datetime.fromisoformat(termin_str)
        return termin_dt.strftime("%d.%m.%Y. u %H:%M")
    except Exception:
        return termin_str

def posalji_mail_nova_rezervacija(data):
    termin_lijepo = formatiraj_termin(data.get('Termin'))
    poruka = f"""
📅 NOVA REZERVACIJA

Ime i prezime: {data.get('Ime')}
Broj telefona: {data.get('Broj')}
Usluga: {data.get('Usluga')}
Termin: {termin_lijepo}
"""
    msg = MIMEText(poruka)
    msg["Subject"] = "💅 Nova rezervacija - Beauty Studio Renea"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("✅ E-mail poslan (nova rezervacija).")
    except Exception as e:
        print("❌ Greška pri slanju e-maila:", e)

def posalji_mail_otkazivanje(data):
    termin_lijepo = formatiraj_termin(data.get('Termin'))
    poruka = f"""
❌ REZERVACIJA OTKAZANA

Ime i prezime: {data.get('Ime')}
Broj telefona: {data.get('Broj')}
Usluga: {data.get('Usluga')}
Termin: {termin_lijepo}
Vrijeme otkazivanja: {datetime.now().strftime('%d.%m.%Y. u %H:%M')}
"""
    msg = MIMEText(poruka)
    msg["Subject"] = "❌ Otkazana rezervacija - Beauty Studio Renea"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print("✅ E-mail poslan (otkazivanje).")
    except Exception as e:
        print("❌ Greška pri slanju e-maila za otkazivanje:", e)

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

    # Dodaj status ako ga nema
    if "Status" not in data:
        data["Status"] = "Aktivno"

    # Spremi u MongoDB
    collection.insert_one(data)

    # Pošalji mail za novu rezervaciju
    posalji_mail_nova_rezervacija(data)

    return jsonify({"message": "Rezervacija spremljena i e-mail poslan!"}), 201

# Ruta za dohvat svih rezervacija (za admin)
@app.route("/rezervacije", methods=["GET"])
def get_rezervacije():
    rezervacije = list(collection.find({}, {"_id": 0}).sort("Termin"))
    return jsonify(rezervacije)

# ➤ NOVO: Ruta za dohvat rezervacija za određenog korisnika (po broju)
@app.route("/rezervacije/korisnik", methods=["GET"])
def rezervacije_korisnika():
    broj = request.args.get("broj")
    if not broj:
        return jsonify({"error": "Nedostaje broj telefona."}), 400
    rezervacije = list(collection.find({"Broj": broj}, {"_id": 0}).sort("Termin"))
    return jsonify(rezervacije)

# ➤ NOVO: Ruta za otkazivanje rezervacije (do 2 sata prije termina)
@app.route("/rezervacije/otkazi", methods=["POST"])
def otkazi_rezervaciju():
    data = request.json
    broj = data.get("broj")
    termin = data.get("termin")  # ISO string

    if not (broj and termin):
        return jsonify({"error": "Nedostaje podatak."}), 400

    rezervacija = collection.find_one({"Broj": broj, "Termin": termin})

    if not rezervacija:
        return jsonify({"error": "Rezervacija nije pronađena."}), 404

    # Već otkazana?
    if rezervacija.get("Status") == "Otkazano":
        return jsonify({"error": "Rezervacija je već otkazana."}), 400

    # Provjeri može li se otkazati (više od 2h prije termina)
    try:
        vrijeme_termina = datetime.fromisoformat(termin)
    except Exception:
        return jsonify({"error": "Nevažeći format termina."}), 400

    sad = datetime.now()
    if vrijeme_termina - sad < timedelta(hours=2):
        return jsonify({"error": "Otkazivanje više nije moguće (manje od 2h do termina)."}), 403

    # Otkazivanje: ažuriraj status na "Otkazano"
    collection.update_one(
        {"Broj": broj, "Termin": termin},
        {"$set": {"Status": "Otkazano"}}
    )

    # Pošalji mail o otkazivanju (koristi podatke iz stare rezervacije)
    rezervacija["Status"] = "Otkazano"
    posalji_mail_otkazivanje(rezervacija)

    return jsonify({"message": "Rezervacija je otkazana!"}), 200

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
