# ─────────────────────────────────────────────────────────────────────────
# app/routers/global_settings.py — Globalne nastavitve (samo glavni admin)
#
# Stran /global-settings: kjer glavni admin nastavi globalni (main admin)
# e-poštni (SMTP) račun za pošiljanje in BACKUP_EMAIL (varnostno kopiranje
# CELOTNE baze — vse šole — pošlje se prek tega main admin e-poštnega računa).
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import User
from app.security import get_current_user_id, sign_user_id
from app.tenancy import MAIN_ADMIN_ROLE, is_main_admin
from app.audit import log_audit
from app.templating import make_templates
from app.app_settings import (
    global_mail_config,
    get_global_backup_email,
    save_global_mail,
)
from app.config import settings

router = APIRouter(tags=["global-settings"])
templates = make_templates()


def _require_main_admin(request: Request, db: Session) -> User:
    """Vrni prijavljenega glavnega admina ali 403/redirect."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not is_main_admin(user):
        raise HTTPException(status_code=403, detail="Dostop samo za glavnega admina")
    return user


@router.get("/global-settings", response_class=HTMLResponse)
def global_settings_page(request: Request, db: Session = Depends(get_db)):
    """Stran z globalnimi nastavitvami (samo glavni admin)."""
    user = _require_main_admin(request, db)
    mail = global_mail_config(db)
    backup_email = get_global_backup_email(db)
    return templates.TemplateResponse("global_settings.html", {
        "request": request,
        "user": user,
        "mail": mail,
        "backup_email": backup_email,
        "inactivity_timeout_ms": (int(getattr(settings, "INACTIVITY_TIMEOUT_ADMIN_MINUTES", 20)) * 60 * 1000),
    })


@router.post("/api/global-settings")
async def update_global_settings(request: Request, db: Session = Depends(get_db)):
    """Shrani globalne SMTP + backup nastavitve (glavni admin)."""
    user = _require_main_admin(request, db)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    port_raw = str(body.get("port", "")).strip()
    try:
        port = int(port_raw) if port_raw else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="MAIL_PORT mora biti številka")

    # Geslo: prazno / "_" → pusti obstoječe (nikoli se ne predizpolni v obrazcu).
    password = str(body.get("password", "")).strip()
    if not password:
        password = None

    save_global_mail(
        db,
        server=str(body.get("server", "")).strip(),
        port=port,
        username=str(body.get("username", "")).strip(),
        password=password,
        from_addr=str(body.get("from", "")).strip(),
        backup_email=str(body.get("backup_email", "")).strip(),
    )
    db.commit()

    log_audit(db, user.id, user.username, "update_global_settings",
              "server=" + str(body.get("server", "")).strip())
    mail = global_mail_config(db)
    return {"ok": True, "mail": mail, "backup_email": get_global_backup_email(db)}


@router.post("/api/global-settings/backup")
def backup_all_schools(request: Request, db: Session = Depends(get_db)):
    """Naredi .sql CELOTNE baze (vse šole) in ga pošlje na BACKUP_EMAIL
    prek globalnega main admin SMTP računa (glavni admin)."""
    user = _require_main_admin(request, db)
    sent, message = _dump_and_send(db)
    status = 200 if sent else 500
    if sent:
        log_audit(db, user.id, user.username, "global_backup", "email=" + get_global_backup_email(db))
    return JSONResponse({"sent": sent, "message": message}, status_code=status)


def _dump_and_send(db: Session):
    """pg_dump celotne baze → priloga .sql → SMTP (globalne nastavitve)."""
    import os, subprocess
    import ssl, smtplib
    import datetime
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    mail = global_mail_config(db)
    to = get_global_backup_email(db)

    if not to:
        return False, "BACKUP_EMAIL ni nastavljen (Globalne nastavitve)."
    if not mail["password"]:
        return False, "SMTP geslo ni nastavljeno (Globalne nastavitve → E-pošta)."

    url = settings.DATABASE_URL or ""
    if "postgresql" not in url:
        return False, "DATABASE_URL ni PostgreSQL — backup ni mogoč."
    parts = url.replace("postgresql://", "").split("@")
    if len(parts) != 2:
        return False, "Neveljaven DATABASE_URL."
    user_pass = parts[0].split(":", 1)
    host_db = parts[1].split("/", 1)
    host_port = host_db[0].split(":", 1)
    username = user_pass[0]
    password_db = user_pass[1] if len(user_pass) > 1 else ""
    host = host_port[0]
    port_db = host_port[1] if len(host_port) > 1 else "5432"
    database = host_db[1] if len(host_db) > 1 else "sola"

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"sola-backup-{ts}.sql"

    env = os.environ.copy()
    if password_db:
        env["PGPASSWORD"] = password_db

    try:
        result = subprocess.run(
            ["pg_dump", "-h", host, "-p", port_db, "-U", username, "-d", database, "-F", "p"],
            env=env, capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:
        return False, f"pg_dump ni mogel steči: {exc}"
    if result.returncode != 0:
        return False, f"pg_dump napaka: {(result.stderr or '')[:300]}"

    size = len(result.stdout.encode("utf-8"))
    msg = MIMEMultipart()
    msg["Subject"] = f"🛡️ Varnostna kopija CELOTNE baze ({ts})"
    msg["From"] = mail["from"]
    msg["To"] = to
    msg.attach(MIMEText(
        "Varnostna kopija cele baze (vse šole).\n"
        f"Datoteka: {filename}\nVelikost: {size} B\n"
        f"Ustvarjeno: {ts}",
        "plain", "utf-8"))
    attachment = MIMEApplication(result.stdout.encode("utf-8"), _subtype="sql")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(mail["server"], mail["port"], timeout=60) as s:
            s.starttls(context=ctx)
            s.login(mail["username"], mail["password"])
            s.send_message(msg)
    except Exception as exc:
        return False, f"Pošiljanje ni uspelo: {exc}"

    return True, f"Backup poslan na {to} ({size} B, {filename})."