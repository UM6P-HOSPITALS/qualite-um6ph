import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


def send_email(to: str, subject: str, body: str) -> bool:
    """Envoie un email. Ne lève jamais d'exception vers l'appelant : une
    erreur SMTP est loguée mais ne doit jamais faire échouer le reste
    d'une requête (ex: la création d'un document ne doit pas planter
    parce que le serveur mail est en panne)."""
    if not settings.smtp_host:
        print(f"[email désactivé — SMTP non configuré] à {to} : {subject}")
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 -- volontairement large, ne doit jamais remonter
        print(f"[erreur envoi email à {to}] {exc}")
        return False
