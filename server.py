from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os
from dotenv import load_dotenv
import logging

# =============== INIT ===================
load_dotenv()  # Lädt Umgebungsvariablen aus .env (lokal) oder Render Environment

app = FastAPI()

# =============== CORS ===================
# Wichtig, damit dein React-Frontend mit dem Backend sprechen darf
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # später kannst du hier z. B. ["https://www.izenic.com"] eintragen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============== MAIL KONFIGURATION ===================
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 465)),   # Standard-Port 465 für SSL
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "False").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "True").lower() == "true",
    USE_CREDENTIALS=True,
)

# =============== MODEL ===================
class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str

# =============== ROUTES ===================
@app.get("/")
def root():
    return {"status": "ok", "message": "IZENIC Backend läuft."}

@app.post("/api/contact")
async def send_contact(form: ContactForm):
    """
    Empfängt Kontaktformular-Daten vom Frontend und sendet E-Mail an kontakt@izenic.com
    """
    try:
        message = MessageSchema(
            subject=f"Neue Anfrage von {form.name}",
            recipients=["kontakt@izenic.com"],  # Zieladresse(n)
            body=f"Von: {form.name} <{form.email}>\n\n{form.message}",
            subtype="plain"
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        logging.info(f"Mail erfolgreich gesendet von {form.email}")
        return {"status": "ok"}
    except Exception as e:
        logging.exception("Mail senden fehlgeschlagen")
        raise HTTPException(status_code=500, detail=f"Fehler beim Mailversand: {str(e)}")

# =============== ERROR HANDLER ===================
@app.get("/health")
def health_check():
    """Health Endpoint für Render oder Überwachung"""
    return {"status": "healthy"}
