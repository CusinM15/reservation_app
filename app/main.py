from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db
from app.routers import rezervacije, ocenjevanja, auth, blocked_dates
from app.models import User, RoleEnum
from passlib.context import CryptContext

app = FastAPI(title="Šolski App", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")

# Authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        public = ["/auth/login", "/health", "/", "/api/razredi", "/api/prostori", "/api/schedule"]
        is_public = any(path == p for p in public) or path.startswith("/static")
        if not is_public and not request.cookies.get("user_id"):
            return RedirectResponse(url="/auth/login")
        return await call_next(request)

app.add_middleware(AuthMiddleware)

@app.on_event("startup")
def on_startup():
    init_db()
    # Create admin user if not exists
    from app.database import SessionLocal
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin = User(
            username="admin",
            email="admin@ostonecufar.local",
            first_name="Admin",
            last_name="OŠ",
            password_hash=pwd_context.hash("admin123"),
            role=RoleEnum.admin,
            is_active=True
        )
        db.add(admin)
        db.commit()
    db.close()

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

@app.get("/")
def root(request: Request):
    user_id = request.cookies.get("user_id")
    if user_id:
        return templates.TemplateResponse("index.html", {"request": request})
    return RedirectResponse(url="/auth/login")

@app.get("/admin/users")
def admin_users_redirect(request: Request):
    return RedirectResponse(url="/auth/admin/users")

@app.get("/api/razredi")
def get_razredi():
    return settings.RAZREDI

@app.get("/api/prostori")
def get_prostori():
    return settings.PROSTORI

@app.get("/api/schedule")
def get_schedule():
    return settings.SCHEDULE

# Include routers
app.include_router(rezervacije.router)
app.include_router(ocenjevanja.router)
app.include_router(auth.router)
app.include_router(blocked_dates.router)
