# ─────────────────────────────────────────────────────────────────────────
# app/main.py — Vstopna točka aplikacije Šolski App za OŠ Toneta Čufarja
#
# Namen: Definira FastAPI aplikacijo, vključuje middleware za avtentikacijo,
# inicializira bazo ob zagonu in poveže vse routerje (rezervacije,
# ocenjevanja, auth, zasedeni datumi, audit log, izvoz, dokumentacija).
#
# Zakaj? Aplikacija mora delovati kot enotna FastAPI storitev, kjer so
# vse poti (UI + API) pod isto domeno. Zato uporabljamo piškotke za
# seje (ne JWT) — aplikacija je namenjena ozkemu krogu uporabnikov
# znotraj šole, kjer so piškotki enostavnejši za implementacijo.
# ─────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db
from app.routers import rezervacije, ocenjevanja, auth, blocked_dates, audit_log, export, docs
from app.audit import log_audit
from app.models import User, RoleEnum
from passlib.context import CryptContext

# ── Inicializacija aplikacije ──────────────────────────────────────────
# Ustvarimo FastAPI instanco z naslovom "Šolski App". Predpone /api/*
# uporabljajo routerji; korenske poti (/ , /health, /history) so definirane tukaj.
app = FastAPI(title="Šolski App", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")

# ── Auth middleware ────────────────────────────────────────────────────
# Zakaj lastni middleware namesto OAuth2/JWT?
# Ker aplikacija uporablja piškotke za sledenje seji (preprosteje za šolsko
# okolje). Middleware preveri, ali ima vsak zahtevan klic piškotek 'user_id'.
# Če ga ni in pot ni javna, preusmeri na login.
#
# Pomembno: To ni varnostna meja — to je UX meja. Resnična avtorizacija
# se dogaja v vsakem routerju posebej (preverjanje vlog).
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Seznam javnih poti — ne zahtevajo prijave.
        # Sem spadajo: login, pozabljeno geslo, zdravstveni endpoint,
        # glavna stran, zgodovina (history), API za razrede/prostore/urnik,
        # ter statične datoteke in dokumentacija.
        public = ["/auth/login", "/auth/forgot-password", "/auth/reset-password", "/health", "/", "/history", "/api/razredi", "/api/prostori", "/api/schedule"]
        is_public = any(path == p for p in public) or path.startswith("/static") or path.startswith("/slike") or path.startswith("/docs/")
        if not is_public and not request.cookies.get("user_id"):
            return RedirectResponse(url="/auth/login")
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# ── Zagon aplikacije (startup event) ────────────────────────────────────
# Ob zagonu:
# 1. Inicializiramo bazo (ustvari tabele, če ne obstajajo)
# 2. Ustvarimo admin uporabnika, če še ne obstaja (privzeto geslo: admin123)
#
# Zakaj ustvarjamo admina ob zagonu namesto s seed skripto?
# Ker želimo, da aplikacija deluje 'out of the box' — ko se prvič
# zažene (lokalno ali v k8s), je admin že na voljo. To je v pomoč
# pri razvoju in testiranju.
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
            email=settings.ADMIN_EMAIL,
            first_name="Admin",
            last_name="OŠ",
            password_hash=pwd_context.hash("admin123"),
            role=RoleEnum.admin,
            is_active=True
        )
        db.add(admin)
        db.commit()
    db.close()

# ── Health check ──────────────────────────────────────────────────────
# Uporablja ga Kubernetes za preverjanje, ali aplikacija živi.
# Nič pametnega — samo vrne OK, če FastAPI sploh odgovarja.
@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

# ── Glavna stran / ────────────────────────────────────────────────────
# Če je uporabnik prijavljen (ima piškotek user_id), mu prikažemo
# index.html z ustreznim timeoutom za neaktivnost.
# Admin/vodstvo ima strožji timeout (krajši) kot navadni učitelji.
#
# Zakaj različen timeout? Admini imajo dostop do občutljivejših funkcij
# (brisanje uporabnikov, audit log), zato želimo hitrejšo avtomatsko
# odjavo. Navadni učitelji imajo daljši timeout, ker urejajo urnike
# in pogosto dlje časa razmišljajo med vnosom.
@app.get("/")
def root(request: Request):
    user_id = request.cookies.get("user_id")
    if user_id:
        from app.database import SessionLocal
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(user_id)).first()
        db.close()

        if user and user.role in (RoleEnum.admin, RoleEnum.vodstvo):
            timeout_ms = settings.INACTIVITY_TIMEOUT_ADMIN_MINUTES * 60 * 1000
        else:
            timeout_ms = settings.INACTIVITY_TIMEOUT_MINUTES * 60 * 1000

        return templates.TemplateResponse("index.html", {
            "request": request,
            "inactivity_timeout_ms": timeout_ms
        })
    return RedirectResponse(url="/auth/login")

# ── Preusmeritev admin uporabnikov ────────────────────────────────────
# Obstaja zaradi priročnosti — /admin/users se preusmeri na pravi endpoint.
@app.get("/admin/users")
def admin_users_redirect(request: Request):
    return RedirectResponse(url="/auth/admin/users")

# ── Javni API končne točke za konfiguracijo ──────────────────────────
# Te poti so javne (ni auth middleware-a), ker jih JavaScript v brskalniku
# kliče za prikaz padajočih menijev (razredi, prostori, urnik).
# Podatki so že v Settings, nič občutljivega.
@app.get("/api/razredi")
def get_razredi():
    return settings.RAZREDI

@app.get("/api/prostori")
def get_prostori():
    return settings.PROSTORI

@app.get("/api/schedule")
def get_schedule():
    return settings.SCHEDULE

# ── Zgodovina (audit log za admina) ──────────────────────────────────
# Prikaže HTML stran z audit logom, vendar samo če je prijavljeni
# uporabnik admin. Če ni, vrne 403 Forbidden.
#
# Zakaj posebna pot /history namesto /api/audit-log/page?
# Zgodovinska ujemanje — prejšnja verzija je uporabljala /history in
# uporabniki so se navadili. Oba endpointa obstajata.
@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    """Pokaži audit log — samo za prijavljenega admina."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login")
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user and user.role == RoleEnum.admin:
            users = db.query(User.id, User.username, User.first_name, User.last_name).order_by(User.first_name).all()
            db.close()
            return templates.TemplateResponse("audit_log.html", {"request": request, "users": users})
        db.close()
    except Exception:
        pass
    return HTMLResponse("Dostop samo za admina. Prijavite se kot admin.", status_code=403)

# ── Povezava routerjev ────────────────────────────────────────────────
# Vsak router pokriva svoj del funkcionalnosti. Zakaj ločeni routerji?
# Modularen pristop omogoča lažje vzdrževanje — vsaka datoteka pokriva
# svoj domen (rezervacije, ocenjevanja, avtentikacija, itd.).
# Include routers
app.include_router(rezervacije.router)
app.include_router(ocenjevanja.router)
app.include_router(auth.router)
app.include_router(blocked_dates.router)
app.include_router(audit_log.router)
app.include_router(export.router)
app.include_router(docs.router)

# ── Statične datoteke za dokumentacijo ────────────────────────────────
# Slike iz dokumentacije (v /documentation/slike/) serviramo kot statične
# datoteke pod /slike/, da jih lahko HTML dokumentacija prikazuje.
# Če mapa ne obstaja (npr. v Docker sliki brez dokumentacije), ne mountamo.
# Static files: slike za dokumentacijo
import os
slike_dir = os.path.join(os.path.dirname(__file__), "..", "documentation", "slike")
if os.path.exists(slike_dir):
    app.mount("/slike", StaticFiles(directory=slike_dir), name="slike")
