from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os
from dotenv import load_dotenv
import logging
import json
from typing import List, Optional
from datetime import datetime

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
    VALIDATE_CERTS=os.getenv("MAIL_VALIDATE_CERTS", "True").lower() == "true",
    TIMEOUT=int(os.getenv("MAIL_TIMEOUT", 60)),
)

# =============== MODELS ===================
class ContactForm(BaseModel):
    name: str
    company: str
    email: EmailStr
    phone: Optional[str] = None
    interest: str
    message: str

class CommentCreate(BaseModel):
    name: Optional[str] = "Anonym"
    comment: str
    insightId: str

class Comment(BaseModel):
    id: str
    name: str
    comment: str
    date: str
    insightId: str

# =============== STORAGE ===================
# Einfache JSON-Datei als Datenbank (kann später durch echte DB ersetzt werden)
COMMENTS_FILE = "comments.json"

def load_comments():
    """Lädt alle Kommentare aus der JSON-Datei"""
    if os.path.exists(COMMENTS_FILE):
        try:
            with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Kommentare: {e}")
            return {}
    return {}

def save_comments(comments_dict):
    """Speichert alle Kommentare in die JSON-Datei"""
    try:
        with open(COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(comments_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Fehler beim Speichern der Kommentare: {e}")
        raise

# =============== ROUTES ===================
@app.get("/")
def root():
    return {"status": "ok", "message": "IZENIC Backend läuft."}

@app.post("/api/contact")
async def send_contact(form: ContactForm):
    """
    Empfängt Kontaktformular-Daten vom Frontend und sendet E-Mail an kontakt@izenic.com
    """
    request_id = f"contact-{int(datetime.now().timestamp() * 1000)}"
    try:
        recipients_env = os.getenv("MAIL_TO", "kontakt@izenic.com")
        recipients = [mail.strip() for mail in recipients_env.split(",") if mail.strip()]
        if not recipients:
            raise ValueError("MAIL_TO ist leer oder ungueltig konfiguriert.")

        # Unterstuetzt neue Frontend-Werte und alte Werte (Rueckwaertskompatibilitaet)
        interest_labels = {
            "audit": "KI-Potenzial-Audit",
            "workflow": "Workflow-Automatisierung",
            "retainer": "IZENIC Retainer",
            "peak": "PEAK-Prozess / Erstberatung",
            "advisory": "Strategische KI-Beratung",
            "general": "Allgemeine Anfrage",
            "compliance": "AI Compliance & Governance",
            "agentic": "Agentic Workflow Systems",
            "sovereign": "Sovereign AI / Private AI",
        }
        interest_label = interest_labels.get(form.interest, form.interest)

        fm = FastMail(conf)

        owner_message = MessageSchema(
            subject=f"Neue Kontaktanfrage von {form.name}",
            recipients=recipients,
            body=(
                f"Request-ID: {request_id}\n"
                "Neue Anfrage ueber das Kontaktformular\n\n"
                f"Name: {form.name}\n"
                f"Unternehmen: {form.company}\n"
                f"E-Mail: {form.email}\n"
                f"Telefon: {form.phone or '-'}\n"
                f"Interessensbereich: {interest_label}\n\n"
                "Nachricht:\n"
                f"{form.message}"
            ),
            subtype="plain"
        )
        await fm.send_message(owner_message)
        logging.info("Kontaktanfrage an Empfaenger versendet [%s]", request_id)

        confirmation_sent = False
        try:
            confirmation_message = MessageSchema(
                subject="Danke fuer Ihre Anfrage bei IZENIC",
                recipients=[str(form.email)],
                body=(
                    f"Hallo {form.name},\n\n"
                    "danke fuer Ihre Anfrage. Wir haben Ihre Nachricht erhalten und melden uns in der Regel innerhalb von 24 Stunden bei Ihnen.\n\n"
                    "Ihre Angaben:\n"
                    f"- Unternehmen: {form.company}\n"
                    f"- Interessensbereich: {interest_label}\n"
                    f"- Telefon: {form.phone or '-'}\n\n"
                    "Viele Gruesse\n"
                    "IZENIC"
                ),
                subtype="plain"
            )
            await fm.send_message(confirmation_message)
            confirmation_sent = True
        except Exception:
            # Anfrage soll trotzdem als erfolgreich gelten, wenn nur die Bestaetigung scheitert.
            logging.warning("Bestaetigungsmail konnte nicht gesendet werden [%s]", request_id, exc_info=True)

        return {"status": "ok", "request_id": request_id, "confirmation_sent": confirmation_sent}
    except Exception as e:
        logging.exception("Mailversand fehlgeschlagen [%s]", request_id)
        err_text = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in err_text:
            raise HTTPException(
                status_code=500,
                detail=(
                    "SMTP-SSL Zertifikat konnte nicht verifiziert werden. "
                    "Pruefen Sie MAIL_SERVER/MAIL_PORT oder setzen Sie testweise MAIL_VALIDATE_CERTS=False."
                ),
            )
        raise HTTPException(
            status_code=500,
            detail="Fehler beim Mailversand. Bitte versuchen Sie es spaeter erneut oder schreiben Sie an hello@izenic.de."
        )

# =============== COMMENT ROUTES ===================
@app.get("/api/comments/{insight_id}")
def get_comments(insight_id: str):
    """Gibt alle Kommentare für einen bestimmten Insight zurück"""
    comments_dict = load_comments()
    return comments_dict.get(insight_id, [])

@app.post("/api/comments")
def create_comment(comment_data: CommentCreate):
    """Erstellt einen neuen Kommentar"""
    comments_dict = load_comments()
    
    # Neue Kommentar-ID generieren
    comment_id = f"{int(datetime.now().timestamp() * 1000)}"
    
    new_comment = {
        "id": comment_id,
        "name": comment_data.name or "Anonym",
        "comment": comment_data.comment,
        "date": datetime.now().isoformat(),
        "insightId": comment_data.insightId
    }
    
    # Kommentare für diesen Insight laden oder leere Liste erstellen
    if comment_data.insightId not in comments_dict:
        comments_dict[comment_data.insightId] = []
    
    # Neuen Kommentar hinzufügen (am Anfang für neueste zuerst)
    comments_dict[comment_data.insightId].insert(0, new_comment)
    
    # Speichern
    save_comments(comments_dict)
    
    return new_comment

# =============== ERROR HANDLER ===================
@app.get("/health")
def health_check():
    """Health Endpoint für Render oder Überwachung"""
    return {"status": "healthy"}
