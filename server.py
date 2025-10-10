from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os
from dotenv import load_dotenv
import logging

load_dotenv()

app = FastAPI()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 465)),   # Standardwert 465
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "False").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "True").lower() == "true",
    USE_CREDENTIALS=True,
)

class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str

@app.post("/api/contact")
async def send_contact(form: ContactForm):
    try:
        message = MessageSchema(
            subject=f"Neue Anfrage von {form.name}",
            recipients=["kontakt@izenic.com"],
            body=f"Von: {form.name} <{form.email}>\n\n{form.message}",
            subtype="plain"
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        return {"status": "ok"}
    except Exception as e:
        logging.exception("Mail senden fehlgeschlagen")
        raise HTTPException(status_code=500, detail=str(e))