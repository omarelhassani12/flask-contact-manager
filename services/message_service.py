"""
message_service.py
──────────────────
Email    → Gmail SMTP via smtplib (uses App Password)
WhatsApp → Twilio WhatsApp API (real delivery, no browser needed)

Required environment variables:
    GMAIL_USER, GMAIL_APP_PASSWORD
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
    TWILIO_WHATSAPP_FROM   (e.g. whatsapp:+14155238886)
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class MessageService:

    # ── Email ──────────────────────────────────────────────────
    def send_email(self, to_address: str, subject: str, body: str) -> tuple[bool, str]:
        """Send an email via Gmail SMTP.
        Reads GMAIL_USER and GMAIL_APP_PASSWORD from environment variables.
        """
        gmail_user = os.environ.get("GMAIL_USER", "").strip()
        gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

        if not gmail_user or not gmail_pass:
            return False, (
                "Configuration manquante : définissez les variables d'environnement "
                "GMAIL_USER et GMAIL_APP_PASSWORD."
            )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = to_address

            # Plain-text part
            text_part = MIMEText(body, "plain", "utf-8")
            # HTML part (simple styling)
            html_body = body.replace("\n", "<br>")
            html_part = MIMEText(
                f"""<html><body style="font-family:sans-serif;color:#1f2937;line-height:1.6">
                    {html_body}
                    <hr style="margin-top:2rem;border:none;border-top:1px solid #e5e7eb">
                    <p style="font-size:0.8rem;color:#9ca3af">Envoyé via Gestion de Contacts</p>
                </body></html>""",
                "html", "utf-8"
            )
            msg.attach(text_part)
            msg.attach(html_part)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_pass)
                server.sendmail(gmail_user, to_address, msg.as_string())

            return True, f"E-mail envoyé à {to_address} avec succès."

        except smtplib.SMTPAuthenticationError:
            return False, (
                "Échec d'authentification Gmail. "
                "Vérifiez GMAIL_USER et GMAIL_APP_PASSWORD (mot de passe d'application)."
            )
        except smtplib.SMTPRecipientsRefused:
            return False, f"Adresse e-mail invalide ou refusée : {to_address}"
        except Exception as e:
            return False, f"Erreur lors de l'envoi : {str(e)}"

    # ── WhatsApp (Twilio API) ──────────────────────────────────
    def send_whatsapp(self, phone: str, message: str) -> tuple[bool, str]:
        """Send a WhatsApp message via Twilio.

        Reads from environment variables:
            TWILIO_ACCOUNT_SID   – your Account SID (starts with AC…)
            TWILIO_AUTH_TOKEN    – your Auth Token
            TWILIO_WHATSAPP_FROM – sandbox or approved number,
                                   e.g. whatsapp:+14155238886
        The recipient's phone must include the country code, e.g. +212XXXXXXXXX.
        """
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        auth_token  = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886").strip()

        if not account_sid or not auth_token:
            return False, (
                "Configuration Twilio manquante : définissez TWILIO_ACCOUNT_SID "
                "et TWILIO_AUTH_TOKEN dans votre fichier .env."
            )

        try:
            from twilio.rest import Client
        except ImportError:
            return False, (
                "Le package 'twilio' n'est pas installé. "
                "Exécutez : pip install twilio"
            )

        # Normalise the phone number → whatsapp:+XXXXXXXXXXX
        clean = "".join(c for c in phone if c.isdigit() or c == "+")
        if not clean.startswith("+"):
            clean = "+" + clean
        to_number = f"whatsapp:{clean}"

        try:
            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                from_=from_number,
                body=message,
                to=to_number,
            )
            return True, (
                f"Message WhatsApp envoyé à {to_number}. "
                f"SID : {msg.sid} | Statut : {msg.status}"
            )
        except Exception as e:
            # Twilio raises TwilioRestException with a readable .msg
            error_text = getattr(e, "msg", str(e))
            return False, f"Erreur Twilio : {error_text}"

    # ── WhatsApp deep-link (kept as fallback) ─────────────────
    def build_whatsapp_url(self, phone: str, message: str) -> str:
        """Return a wa.me URL (opens WhatsApp in the browser - fallback only)."""
        import urllib.parse
        clean = "".join(c for c in phone if c.isdigit() or c == "+")
        number = clean.lstrip("+")
        encoded = urllib.parse.quote(message)
        return f"https://wa.me/{number}?text={encoded}"
