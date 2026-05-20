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
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Napačno uporabniško ime ali geslo"}
        )
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id))
    response.set_cookie(key="role", value=user.role)
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
    return {"id": user.id, "username": user.username, "role": user.role}

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
        return RedirectResponse(url="/admin/users?error=Uporabnik že obstaja", status_code=303)
    
    hashed = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed, role=role, is_active=True)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

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
    return RedirectResponse(url="/admin/users", status_code=303)

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
    return RedirectResponse(url="/admin/users", status_code=303)
