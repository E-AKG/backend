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
)

# =============== MODELS ===================
class ContactForm(BaseModel):
    name: str
    email: EmailStr
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

@app.delete("/api/comments/{insight_id}/{comment_id}")
def delete_comment(insight_id: str, comment_id: str):
    """Löscht einen Kommentar"""
    comments_dict = load_comments()
    
    if insight_id not in comments_dict:
        raise HTTPException(status_code=404, detail="Insight nicht gefunden")
    
    # Kommentar finden und entfernen
    comments = comments_dict[insight_id]
    original_length = len(comments)
    comments_dict[insight_id] = [c for c in comments if c["id"] != comment_id]
    
    if len(comments_dict[insight_id]) == original_length:
        raise HTTPException(status_code=404, detail="Kommentar nicht gefunden")
    
    # Speichern
    save_comments(comments_dict)
    
    return {"status": "ok", "message": "Kommentar gelöscht"}

# =============== ERROR HANDLER ===================
@app.get("/health")
def health_check():
    """Health Endpoint für Render oder Überwachung"""
    return {"status": "healthy"}
