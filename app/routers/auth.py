from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os, secrets
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import User, RoleEnum
from app.config import settings, validate_password_strength
from app.routers.blocked_dates import _send_email

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _reset_token_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_EXPIRATION_MINUTES)


def _encode_reset_token(raw_token: str) -> str:
    return f"{raw_token}:{int(_reset_token_expires_at().timestamp())}"


def _decode_reset_token(stored_token: str | None) -> str | None:
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


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None, info: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error, "info": info})


@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Allow login with either username or email
    user = db.query(User).filter(
        ((User.username == username) | (User.email == username)),
        User.is_active == True
    ).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Napačno uporabniško ime ali geslo"}
        )
    
    response = RedirectResponse(url="/", status_code=303)
    # Session cookies - no max_age, deleted on browser close
    response.set_cookie(key="user_id", value=str(user.id), httponly=True, samesite="lax")
    response.set_cookie(key="role", value=user.role, httponly=True, samesite="lax")
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("user_id")
    response.delete_cookie("role")
    return response


@router.get("/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Ni prijavljen")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": full_name,
        "role": user.role,
    }


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, error: str = None, info: str = None):
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
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Uporabnik s tem emailom ne obstaja.",
            "show_forgot": True,
        })
    
    # Generate a reset token. Stored as "<token>:<unix_expires_at>" so old links expire after 30 minutes.
    token = _encode_reset_token(secrets.token_urlsafe(32))
    user.reset_token = token
    db.commit()
    
    # Uporabi trenutno zahtevan URL — deluje na vsaki domeni (ngrok, ostc.si, localhost)
    reset_link = f"{request.base_url}auth/reset-password?token={token}&email={email}"
    
    _send_email(
        to_email=email,
        subject="Ponastavitev gesla - Šolski App",
        body=f"Pozdravljeni {user.first_name} {user.last_name},\n\n"
             f"Prejeli smo zahtevo za ponastavitev gesla.\n\n"
             f"Za ponastavitev gesla kliknite na spodnjo povezavo:\n"
             f"{reset_link}\n\n"
             f"Če niste zahtevali ponastavitve gesla, to sporočilo ignorirajte.\n\n"
             f"Lep pozdrav,\nŠolski App"
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
    stored_token = request.query_params.get("token", "")
    user = db.query(User).filter(User.email == email, User.reset_token == stored_token).first()
    if not user or _decode_reset_token(user.reset_token) != stored_token:
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
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email, User.reset_token == token).first()
    if not user or _decode_reset_token(user.reset_token) != token:
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
    user.reset_token = None
    db.commit()
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "info": "Geslo uspešno spremenjeno. Sedaj se lahko prijavite.",
    })


@router.post("/change-password")
def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.cookies.get("user_id")
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
    return {"message": "Geslo uspešno spremenjeno"}


# Admin endpoints
@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    
    users = db.query(User).all()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})


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
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    
    err = validate_password_strength(password)
    if err:
        return RedirectResponse(url=f"/auth/admin/users?error={err}", status_code=303)
    
    existing = db.query(User).filter(User.username == username).first()
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
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.get("/admin/users/{id}/deactivate")
def deactivate_user(id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    
    user = db.query(User).filter(User.id == id).first()
    if user:
        user.is_active = False
        db.commit()
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.get("/admin/users/{id}/activate")
def activate_user(id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    
    user = db.query(User).filter(User.id == id).first()
    if user:
        user.is_active = True
        db.commit()
    return RedirectResponse(url="/auth/admin/users", status_code=303)


@router.get("/admin/users/{id}/delete")
def delete_user(id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    if current_user.id == id:
        return HTMLResponse("Ne morete izbrisati samega sebe", status_code=400)
    
    user = db.query(User).filter(User.id == id).first()
    if not user:
        return RedirectResponse(url="/auth/admin/users?error=Uporabnik ne obstaja", status_code=303)
    
    # Delete user's reservations and assessments first
    from app.models import Reservation, Assessment
    db.query(Reservation).filter(Reservation.teacher_id == id).delete()
    db.query(Assessment).filter(Assessment.teacher_id == id).delete()
    db.delete(user)
    db.commit()
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
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if current_user.role != RoleEnum.admin:
        return HTMLResponse("Nimate admin pravic", status_code=403)
    
    user = db.query(User).filter(User.id == id).first()
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
    return RedirectResponse(url="/auth/admin/users", status_code=303)
