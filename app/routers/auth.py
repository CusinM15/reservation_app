# ─────────────────────────────────────────────────────────────────────────
# app/routers/auth.py — Avtentikacija in upravljanje uporabnikov
#
# Namen: Prijava, odjava, ponastavitev gesla, sprememba gesla ter admin
# CRUD za uporabnike (ustvarjanje, urejanje, deaktivacija, brisanje).
#
# Zakaj piškotki namesto JWT/tokenov?
# Aplikacija je namenjena ozkemu krogu uporabnikov (učitelji šole).
# Piškotki so enostavnejši — ni potrebe po osveževanju tokenov, ni
# localStorage (manj ranljiv za XSS). httponly in samesite=lax
# zagotavljata osnovno varnost.
#
# Pomembno: Admin račun se ustvari ob prvem zagonu (v main.py).
# Privzeto geslo "admin123" je treba takoj spremeniti!
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os, secrets
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.config import settings
from app.audit import log_audit
from app.models import User, RoleEnum
from app.config import settings, validate_password_strength
from app.routers.blocked_dates import _send_email
from app.security import sign_user_id, get_current_user_id
from app.tenancy import (
    MAIN_ADMIN_ROLE,
    config_for_request,
    find_user_for_login,
    get_request_user,
    is_main_admin,
    is_school_admin,
    request_school_id,
    write_school_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Pomožne funkcije za upravljanje uporabnikov (večšolsko) ─────────
# Uporabnike lahko upravlja ŠOLSKI admin (samo svoja šola) ali GLAVNI admin
# (izbrana šola ali vse šole). Vračamo par (uporabnik, school_id) — None
# pomeni »vse šole« (samo glavni admin).

def _user_admin_scope(request: Request, db: Session):
    """Vrni (current_user, school_id, error_response).

    error_response je HTMLResponse(403), če uporabnik ni admin — s tem
    ohranimo dosedanje vedenje (stran vrne 403, ne JSON napake).
    """
    current = get_request_user(request, db)
    if not current:
        return None, None, HTMLResponse("Nimate admin pravic", status_code=403)
    if is_main_admin(current):
        return current, request_school_id(request), None
    if not is_school_admin(current):
        return current, None, HTMLResponse("Nimate admin pravic", status_code=403)
    return current, current.school_id, None


def _scoped_users(db: Session, school_id: int | None):
    """Poizvedba po uporabnikih, omejena na šolo.

    school_id=None (glavni admin brez izbrane šole) vrne vse ŠOLSKE
    uporabnike — globalnih (glavni admin) ne prikazujemo.
    """
    query = db.query(User)
    if school_id is None:
        return query.filter(User.school_id.isnot(None))
    return query.filter(User.school_id == school_id)


def _find_user_by_email(db: Session, request: Request, email: str, reset_token: str | None = None):
    """Poišči uporabnika po e-pošti (za pozabljeno geslo).

    Če je zahtevek vezan na šolo (URL-alias), iščemo znotraj nje; sicer
    globalno (za eno šolo je zadetek natanko eden — vedenje nespremenjeno).
    """
    query = db.query(User).filter(User.email == email)
    if reset_token is not None:
        query = query.filter(User.reset_token == reset_token)
    school_id = request_school_id(request)
    if school_id is not None:
        query = query.filter((User.school_id == school_id) | (User.school_id.is_(None)))
    return query.first()


# ── Pomožne funkcije za ponastavitev gesla ──────────────────────────
# Token za ponastavitev gesla je shranjen kot "<token>:<unix_expires_at>".
# Zakaj? Tako lahko preverimo veljavnost brez dodatnega DB poizvedovanja
# — če je timestamp potekel, token takoj zavržemo.
# RESET_TOKEN_EXPIRATION_MINUTES = 120 (2 uri) je nastavljeno v config.

def _reset_token_expires_at(config=None) -> datetime:
    """Vrne čas, ko token poteče (sedaj + konfiguriran timeout).

    Timeout je lahko nastavitev šole (SchoolConfig); če ni podana,
    se uporabi vrednost iz .env.
    """
    minutes = config.RESET_TOKEN_EXPIRATION_MINUTES if config is not None \
        else settings.RESET_TOKEN_EXPIRATION_MINUTES
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _encode_reset_token(raw_token: str, config=None) -> str:
    """Zakodira token s časom poteka: 'token:unix_timestamp'."""
    return f"{raw_token}:{int(_reset_token_expires_at(config).timestamp())}"


def _decode_reset_token(stored_token: str | None) -> str | None:
    """Dekodira token in preveri, ali je še veljaven.
    
    Če je token potekel (timestamp je v preteklosti), vrne None.
    Uporabnik mora zahtevati novo povezavo za ponastavitev.
    """
    if not stored_token or ":" not in stored_token:
        return None
    token, expires_at_raw = stored_token.rsplit(":", 1)
    try:
        expires_at = datetime.fromtimestamp(int(expires_at_raw), timezone.utc)
    except ValueError:
        return None
    if expires_at < datetime.now(timezone.utc):
        return None
    return token


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# ── Prijava / odjava ──────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None, info: str = None):
    """Prikaži login stran z morebitnim sporočilom o napaki ali informacijo."""
    return templates.TemplateResponse("login.html", {"request": request, "error": error, "info": info})


@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Obdelava prijave — preveri username/email in geslo, nastavi piškotke.
    
    Dovoljena je prijava z uporabniškim imenom ALI emailom (v username polje).
    To je priročno, ker si učitelji pogosto zapomnijo email namesto username-a.

    Večšolsko: uporabnik se išče v šoli, ki ji pripada zahtevek (URL-alias),
    sicer globalno. Če enako uporabniško ime obstaja v več šolah, prijava
    zahteva pot konkretne šole (jasno sporočilo).
    
    Piškotke nastavimo brez max_age — pomeni, da se izbrišejo ob zaprtju
    brskalnika (session cookies). To je varnostna praksa za javne računalnike.
    """
    # Allow login with either username or email
    try:
        user = find_user_for_login(db, request, username)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": exc.detail},
        )
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Napačno uporabniško ime ali geslo"}
        )
    
    # Glavnega admina peljemo na pregled šol (nima svoje šole/urnika).
    target = "/schools" if is_main_admin(user) else "/rezervacije"
    response = RedirectResponse(url=target, status_code=303)
    # Session cookies - no max_age, deleted on browser close
    # ⚠️ user_id je PODPISAN (itsdangerous) — brez podpisa bi lahko vsak
    # nastavil user_id=1 in postal admin (auth bypass).
    response.set_cookie(key="user_id", value=sign_user_id(user.id), httponly=True, samesite="lax")
    response.set_cookie(key="role", value=user.role, httponly=True, samesite="lax")
    # Če je prijava tekla prek poti šole, si glavni admin zapomni izbrano šolo.
    school_id = request_school_id(request)
    if school_id is not None:
        response.set_cookie(key="school_ctx", value=str(school_id), httponly=True, samesite="lax")
    return response


@router.get("/logout")
def logout():
    """Odjava — pobriše piškotke in preusmeri na login."""
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("user_id")
    response.delete_cookie("role")
    return response


@router.get("/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Vrne podatke o trenutno prijavljenem uporabniku.
    
    Uporablja se iz JavaScript-a za prikaz imena in vloge v UI.
    full_name se izračuna iz first_name + last_name.
    school_id/school_name povesta, kateri šoli uporabnik pripada (glavni
    admin ima school_id = null).
    """
    user = get_request_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ni prijavljen")
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    school_name = None
    if user.school_id:
        from app.models import School
        school = db.query(School).filter(School.id == user.school_id).first()
        school_name = school.name if school else None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": full_name,
        "role": user.role,
        "school_id": user.school_id,
        "school_name": school_name,
        "is_main_admin": is_main_admin(user),
    }


# ── Pozabljeno geslo ─────────────────────────────────────────────────
# Dvostopenjski proces:
# 1. Uporabnik vpiše email -> dobimo token
# 2. Klikne povezavo v emailu -> nastavi novo geslo
#
# Zakaj ne pošiljamo gesla v čisti obliki?
# Varnost — nikoli ne shranjujemo čistih gesel. Token je enkraten in
# poteče po 2 urah. Povezava vsebuje token v URL-ju (kar je sprejemljivo
# za HTTPS).

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, error: str = None, info: str = None):
    """Prikaži obrazec za pozabljeno geslo (znotraj login.html)."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "info": info,
        "show_forgot": True,
    })


@router.post("/forgot-password")
def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """Obdelaj zahtevo za ponastavitev gesla.
    
    Vedno vrne enako sporočilo, tudi če email ne obstaja (varnost —
    ne razkrijemo, kateri emaili so v bazi).
    """
    user = _find_user_by_email(db, request, email)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Uporabnik s tem emailom ne obstaja.",
            "show_forgot": True,
        })
    
    config = config_for_request(request, db)

    # Generate a reset token. Stored as "<token>:<unix_expires_at>" so old links expire after 30 minutes.
    token = _encode_reset_token(secrets.token_urlsafe(32), config)
    user.reset_token = token
    db.commit()
    
    # Zgradi javno dosegljivo povezavo za ponastavitev. Upoštevamo
    # X-Forwarded-Proto/Host (ki pošlje Cloudflare/proxy), da uporabnik
    # dobi JAVNO povezavo (ne notranjo IP). Če proxy ni, pade nazaj na
    # request.url.scheme/netloc. Email URL-encodiramo, da povezava dela
    # tudi za posebne znake v emailu.
    import urllib.parse
    fproto = request.headers.get("x-forwarded-proto") or request.url.scheme
    fhost = request.headers.get("x-forwarded-host") or request.url.netloc
    base = f"{fproto}://{fhost}/"
    reset_link = f"{base}auth/reset-password?token={token}&email={urllib.parse.quote(email)}"
    
    _send_email(
        to_email=email,
        subject="Ponastavitev gesla - Šolski App",
        body=f"Pozdravljeni {user.first_name} {user.last_name},\n\n"
             f"Prejeli smo zahtevo za ponastavitev gesla.\n\n"
             f"Za ponastavitev gesla kliknite na spodnjo povezavo:\n"
             f"{reset_link}\n\n"
             f"Če niste zahtevali ponastavitve gesla, to sporočilo ignorirajte.\n\n"
             f"Lep pozdrav,\nŠolski App",
        config=config,
    )
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "info": "Če email obstaja v sistemu, smo vam poslali povezavo za ponastavitev gesla.",
    })


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    token: str = "",
    email: str = "",
    error: str = None,
    db: Session = Depends(get_db),
):
    """Prikaži obrazec za novo geslo (če je token veljaven)."""
    stored_token = request.query_params.get("token", "")
    user = _find_user_by_email(db, request, email, reset_token=stored_token)
    if not user or _decode_reset_token(user.reset_token) is None:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Neveljavna ali potekla povezava za ponastavitev gesla.",
        })
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "show_reset": True,
        "reset_token": token,
        "reset_email": email,
    })


@router.post("/reset-password")
def reset_password(
    request: Request,
    token: str = Form(...),
    email: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Obdelaj nastavitev novega gesla.
    
    Preveri ujemanje gesel, moč gesla in veljavnost tokena.
    Po uspešni spremembi token pobrišemo (enkratna uporaba).
    """
    if new_password != confirm_password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Gesli se ne ujemata.",
            "show_reset": True,
            "reset_token": token,
            "reset_email": email,
        })
    user = _find_user_by_email(db, request, email, reset_token=token)
    if not user or _decode_reset_token(user.reset_token) is None:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Neveljavna ali potekla povezava za ponastavitev gesla.",
        })
    
    # Validate new password
    err = validate_password_strength(new_password)
    if err:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": err,
            "show_reset": True,
            "reset_token": token,
            "reset_email": email,
        })
    
    user.password_hash = get_password_hash(new_password)
    user.reset_token = None  # token je enkraten — pobrišemo ga
    db.commit()
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "info": "Geslo uspešno spremenjeno. Sedaj se lahko prijavite.",
    })


# ── Sprememba gesla (prijavljen uporabnik) ──────────────────────────

@router.post("/change-password")
def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Sprememba gesla za trenutno prijavljenega uporabnika.
    
    Zahteva staro geslo za potrditev identitete. Beležimo v audit log.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Staro geslo ni pravilno")
    
    err = validate_password_strength(new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    user.password_hash = get_password_hash(new_password)
    db.commit()
    log_audit(db, user_id=user.id, username=user.username,
              action="change_password",
              details="user changed own password")
    return {"message": "Geslo uspešno spremenjeno"}


# ═══════════════════════════════════════════════════════════════════════
# Admin endpointi za upravljanje uporabnikov
# ═══════════════════════════════════════════════════════════════════════
# Uporabnike upravlja ŠOLSKI admin (samo svoja šola) ali GLAVNI admin
# (izbrana šola oz. vse šole). Vodstvo in učitelji nimajo dostopa.
#
# Izolacija: vsaka poizvedba in vsak zapis je omejen na šolo (school_id),
# zato šolski admin ne more videti ali spreminjati uporabnikov druge šole.

# Vloge, ki jih sme podeliti šolski admin. main_admin lahko podeli samo
# glavni admin (globalna vloga).
_SCHOOL_ROLES = {RoleEnum.teacher.value, RoleEnum.vodstvo.value, RoleEnum.admin.value}


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, db: Session = Depends(get_db)):
    """Prikaži seznam uporabnikov šole, ki jo admin upravlja."""
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/auth/login")
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error

    users = _scoped_users(db, school_id).order_by(User.first_name).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "users": users,
        "is_main_admin": is_main_admin(current_user),
        "school_id": school_id,
    })


@router.post("/admin/users")
def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    """Ustvari novega uporabnika (šolski admin svoje šole, glavni admin poljubne).
    
    Preveri moč gesla in unikatnost uporabniškega imena ZNOTRAJ šole.
    Če email ni podan, shranimo None (ni obvezen).
    """
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error

    if role not in _SCHOOL_ROLES and not is_main_admin(current_user):
        return RedirectResponse(url="/auth/admin/users?error=Neveljavna vloga", status_code=303)

    target_school_id = school_id
    if target_school_id is None and role != MAIN_ADMIN_ROLE:
        return RedirectResponse(
            url="/auth/admin/users?error=Najprej izberite šolo (pot šole).", status_code=303
        )

    err = validate_password_strength(password)
    if err:
        return RedirectResponse(url=f"/auth/admin/users?error={err}", status_code=303)
    
    # Unikatnost velja ZNOTRAJ šole.
    existing = db.query(User).filter(
        User.username == username, User.school_id == target_school_id
    ).first()
    if existing:
        return RedirectResponse(url="/auth/admin/users?error=Uporabnik že obstaja", status_code=303)
    
    hashed = get_password_hash(password)
    new_user = User(
        username=username,
        email=email or None,
        first_name=first_name,
        last_name=last_name,
        password_hash=hashed,
        role=role,
        is_active=True,
        school_id=target_school_id,
    )
    db.add(new_user)
    db.commit()
    log_audit(db, user_id=current_user.id, username=current_user.username,
              action="create_user",
              details=f"username={username}, email={email}, role={role}, school_id={target_school_id}",
              school_id=target_school_id)
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.post("/admin/users/import")
async def import_users_csv(request: Request, db: Session = Depends(get_db)):
    """Uvozi uporabnike iz CSV datoteke (šolski admin svoje šole).

    Pripravljeno za UI (gumb »Uvozi CSV«), ki ga lahko dodamo kasneje.
    Pričakovane glave stolpcev (neobčutljivo na velikost črk, vrstni red
    dowoln): username, email, first_name, last_name, role, password.
    Če gesla ni, se uporabniku nastavi privzeto geslo, ki ga mora zamenjati.

    Vrne JSON povzetek: {created, skipped, errors}.
    """
    import csv
    import io

    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        raise HTTPException(status_code=403, detail="Nimate admin pravic")
    if school_id is None:
        raise HTTPException(status_code=400, detail="Najprej izberite šolo (pot šole).")

    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Manjka datoteka (polje 'file').")

    raw = await upload.read()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):  # 2 = prva vrstica pod glavo
        norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        username = norm.get("username", "")
        if not username:
            errors.append(f"vrstica {i}: manjka username")
            continue
        role = norm.get("role") or RoleEnum.teacher.value
        if role not in _SCHOOL_ROLES:
            errors.append(f"vrstica {i}: neveljavna vloga '{role}'")
            continue
        exists = db.query(User).filter(
            User.username == username, User.school_id == school_id
        ).first()
        if exists:
            skipped += 1
            continue
        password = norm.get("password") or settings.DEFAULT_IMPORT_PASSWORD
        db.add(User(
            school_id=school_id,
            username=username,
            email=norm.get("email") or None,
            first_name=norm.get("first_name", ""),
            last_name=norm.get("last_name", ""),
            password_hash=get_password_hash(password),
            role=role,
            is_active=True,
        ))
        created += 1

    db.commit()
    log_audit(db, user_id=current_user.id, username=current_user.username,
              action="import_users", details=f"school_id={school_id}, created={created}, skipped={skipped}",
              school_id=school_id)
    return {"created": created, "skipped": skipped, "errors": errors}


@router.post("/admin/users/{id}/deactivate")
def deactivate_user(id: int, request: Request, db: Session = Depends(get_db)):
    """Deaktiviraj uporabnika (ne izbriše — samo onemogoči prijavo).
    
    Zakaj deaktivacija namesto brisanja? Da ohranimo zgodovinske povezave
    (rezervacije ostanejo v bazi). Deaktiviran uporabnik se ne more
    prijaviti, vendar njegove rezervacije ostanejo vidne.
    """
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error
    
    user = _scoped_users(db, school_id).filter(User.id == id).first()
    if user:
        user.is_active = False
        db.commit()
        log_audit(db, user_id=current_user.id, username=current_user.username,
                  action="deactivate_user",
                  details=f"user_id={id}, username={user.username}",
                  school_id=user.school_id)
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.post("/admin/users/{id}/activate")
def activate_user(id: int, request: Request, db: Session = Depends(get_db)):
    """Ponovno aktiviraj deaktiviranega uporabnika."""
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error
    
    user = _scoped_users(db, school_id).filter(User.id == id).first()
    if user:
        user.is_active = True
        db.commit()
        log_audit(db, user_id=current_user.id, username=current_user.username,
                  action="activate_user",
                  details=f"user_id={id}, username={user.username}",
                  school_id=user.school_id)
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.post("/admin/users/{id}/delete")
def delete_user(id: int, request: Request, db: Session = Depends(get_db)):
    """Izbriši uporabnika in njegove rezervacije/ocenjevanja.
    
    OPOZORILO: Brisanje je trajno! Pred brisanjem pobrišemo tudi vse
    rezervacije in ocenjevanja, ki jih je uporabnik ustvaril.
    Admin ne more izbrisati samega sebe (zaščita). Šolski admin ne more
    izbrisati uporabnika druge šole (iskanje je omejeno na njegovo šolo).
    """
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error
    if current_user.id == id:
        return HTMLResponse("Ne morete izbrisati samega sebe", status_code=400)
    
    user = _scoped_users(db, school_id).filter(User.id == id).first()
    if not user:
        return RedirectResponse(url="/auth/admin/users?error=Uporabnik ne obstaja", status_code=303)
    
    # Delete user's reservations and assessments first (znotraj njegove šole).
    from app.models import Reservation, Assessment
    db.query(Reservation).filter(
        Reservation.teacher_id == id, Reservation.school_id == user.school_id
    ).delete()
    db.query(Assessment).filter(
        Assessment.teacher_id == id, Assessment.school_id == user.school_id
    ).delete()
    db.delete(user)
    db.commit()
    log_audit(db, user_id=current_user.id, username=current_user.username,
              action="delete_user",
              details=f"user_id={id}, username={user.username}, role={user.role}",
              school_id=user.school_id)
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.post("/admin/users/{id}/update")
def update_user(
    id: int,
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    role: str = Form(...),
    new_password: str = Form(""),
    db: Session = Depends(get_db)
):
    """Posodobi podatke uporabnika (šolski admin svoje šole).
    
    Če new_password ni prazen, spremeni tudi geslo.
    Sicer geslo ostane nespremenjeno.
    """
    current_user, school_id, error = _user_admin_scope(request, db)
    if error is not None:
        return error

    if role not in _SCHOOL_ROLES and not is_main_admin(current_user):
        return RedirectResponse(url="/auth/admin/users?error=Neveljavna vloga", status_code=303)
    
    user = _scoped_users(db, school_id).filter(User.id == id).first()
    if not user:
        return RedirectResponse(url="/auth/admin/users?error=Uporabnik ne obstaja", status_code=303)
    
    if new_password:
        err = validate_password_strength(new_password)
        if err:
            return RedirectResponse(url=f"/auth/admin/users?error={err}", status_code=303)
        user.password_hash = get_password_hash(new_password)
    
    user.username = username
    user.email = email or None
    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    db.commit()
    log_audit(db, user_id=current_user.id, username=current_user.username,
              action="update_user",
              details=f"user_id={id}, username={username}, email={email}, role={role}, password_changed={'yes' if new_password else 'no'}",
              school_id=user.school_id)
    return RedirectResponse(url="/auth/admin/users", status_code=303)
