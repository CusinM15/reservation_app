from fastapi import APIRouter, Request, Depends, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os

from app.database import get_db
from app.models import User, RoleEnum

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

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
    # Session cookies - brez max_age, izbrišejo se ob zaprtju brskalnika
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
        is_active=True
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
    
    user.username = username
    user.email = email or None
    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    if new_password:
        user.password_hash = get_password_hash(new_password)
    db.commit()
    return RedirectResponse(url="/auth/admin/users", status_code=303)
