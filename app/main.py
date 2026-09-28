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

from fastapi import FastAPI, Request, Query, Depends
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.database import init_db, get_db, SessionLocal
from app.routers import rezervacije, ocenjevanja, auth, blocked_dates, audit_log, export, docs, dejavnosti, schools, subscription
from app.app_settings import selling_enabled
from app.subscriptions import is_active
from app.models import User, RoleEnum
from app.tenancy import (
    MAIN_ADMIN_ROLE,
    SCHOOL_ADMIN_ROLE,
    bootstrap_tenancy,
    config_for_request,
    is_main_admin,
    parse_alias_path,
    lookup_alias_school_id,
    nav_paths,
    resolve_school_context,
    role_value,
)

# Sporočilo, ki ga uporabnik vidi, ko šola nima veljavne naročnine.
NAROCNINA_POTEKLA = (
    "Naro%C4%8Dnina+%C5%A1ole+je+potekla.+Za+obnovitev+se+obrnite+na+"
    "administratorja+%C5%A1ole."
)


def subscription_blocks_access(request: Request) -> bool:
    """Ali naj bo ta zahteva zavrnjena, ker šola nima veljavne naročnine?

    Preverjanje je namenoma poceni: ko je prodaja izklopljena (privzeto), se
    takoj vrne False, ne da bi se dotaknili baze (stikalo je predpomnjeno).
    Dovoljeni so: glavni admin in ŠOLSKI ADMIN (ta mora priti do nakupa).
    """
    db = SessionLocal()
    try:
        if not selling_enabled(db):
            return False
        uid = get_current_user_id(request)
        if not uid:
            return False
        user = db.query(User).filter(User.id == uid).first()
        if user is None or is_main_admin(user) or role_value(user) == SCHOOL_ADMIN_ROLE:
            return False
        if user.school_id is None:          # npr. glavni admin brez šole
            return False
        return not is_active(db, user.school_id)
    finally:
        db.close()

# ── Inicializacija aplikacije ──────────────────────────────────────────
# Ustvarimo FastAPI instanco z naslovom "Šolski App". Predpone /api/*
# uporabljajo routerji; korenske poti (/ , /health, /history) so definirane tukaj.
app = FastAPI(title="Šolski App", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")


# ── Middleware: šolski URL-aliasi ──────────────────────────────────────
# Vsaka šola ima svoje poti (npr. /ocenjevanje_ostcj, /rezervacije_ostc).
# Ta middleware prvi segment prevede na kanonično pot in v scope zapiše
# school_id. Kanonične poti (/rezervacije, /ocenjevanje, ...) ostanejo
# nespremenjene — zato se za obstoječo šolo vidno nič ne spremeni.
#
# Zakaj ASGI middleware in ne BaseHTTPMiddleware? Ker želimo pot
# prepisati PRED usmerjanjem (routing), kar je v čistem ASGI sloju
# najbolj neposredno.
class SchoolAliasMiddleware:
    """Prepiše pot šole (alias) v kanonično pot IN si zapomni izbrano šolo.

    Zakaj piškotek school_ctx? Stran se naloži z ENO zahtevo (na pot šole),
    podatke pa nato pripelje JavaScript z ločenimi klici na /api/... — ti
    klici ne vsebujejo imena poti šole. Brez piškotka je glavni admin na
    /rezervacije_st videl podatke vseh šol (ali prejšnje izbrane šole), kar je
    bilo videti, kot da poti šol ne delujejo oz. da se mešajo šole. Piškotek
    torej izbrano šolo ohrani skozi celotno sejo, tudi za API klice.

    Varnost: piškotek NE more razkriti podatkov druge šole. Za šolske
    uporabnike je obseg vedno vezan na user.school_id (glej data_school_id);
    če se kontekst razlikuje, sledi 403. Piškotek torej izbira le, kaj gleda
    glavni admin.
    """

    COOKIE_NAME = "school_ctx"
    COOKIE_MAX_AGE = 60 * 60 * 12      # 12 ur (en delovni dan)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        alias, canonical = parse_alias_path(scope.get("path", ""))
        school_id = None
        if alias and canonical:
            school_id = lookup_alias_school_id(alias)
            if school_id is not None:
                scope["path"] = canonical
                scope["raw_path"] = canonical.encode("utf-8")
                state = scope.setdefault("state", {})
                state["school_id"] = school_id
                state["school_alias"] = alias

        if school_id is None:
            return await self.app(scope, receive, send)

        cookie_value = (
            f"{self.COOKIE_NAME}={school_id}; Path=/; "
            f"Max-Age={self.COOKIE_MAX_AGE}; SameSite=Lax; HttpOnly"
        ).encode("latin-1")

        async def send_with_cookie(message):
            # Piškotek pripnemo na odgovor (ASGI sloj ne pozna Response objektov).
            if message["type"] == "http.response.start":
                headers = [
                    (k, v) for (k, v) in message.get("headers", [])
                    if not (k.lower() == b"set-cookie"
                            and v.startswith(f"{self.COOKIE_NAME}=".encode("latin-1")))
                ]
                headers.append((b"set-cookie", cookie_value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)


app.add_middleware(SchoolAliasMiddleware)

# ── Stiskanje odgovorov (gzip) ─────────────────────────────────────────
# Zakaj? Stran s koledarjem in JSON-odgovori so besedilo (HTML/JSON) in se
# stisnejo na ~10–20 % velikosti. Kjer je strežnik blizu (k3s v šoli) to ni
# opazno, pri gostovanju na daljavo (Railway + domači internet) pa se prenos
# občutno skrajša. Prag 1000 B pomeni, da majhnih odgovorov ne stiskamo.
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
        public = ["/auth/login", "/auth/forgot-password", "/auth/reset-password", "/health", "/", "/history", "/api/razredi", "/api/prostori", "/api/schedule", "/nakup", "/registracija"]
        is_public = any(path == p for p in public) or path.startswith("/static") or path.startswith("/slike") or path.startswith("/docs/")
        if not is_public and not get_current_user_id(request):
            return RedirectResponse(url="/auth/login")

        # ── Naročnina ──────────────────────────────────────────────────
        # Če šola nima veljavne naročnine, aplikacija zanjo ni več dostopna:
        # prijavita se lahko le ŠOLSKI ADMIN (da kupi nov mesec) in glavni
        # admin. Preverjamo v middleware, da velja tudi za že odprte seje.
        # Ko je prodaja izklopljena (privzeto, npr. v šolski namestitvi),
        # preverjanje ne stori nič in ne obremenjuje baze.
        if (not is_public and not path.startswith("/narocnina")
                and not path.startswith("/auth") and get_current_user_id(request)):
            if subscription_blocks_access(request):
                if path.startswith("/api/"):
                    return JSONResponse(
                        {"detail": "Naročnina šole je potekla. Za obnovitev se "
                                   "obrnite na administratorja šole."},
                        status_code=403,
                    )
                return RedirectResponse(url=f"/narocnina?error={NAROCNINA_POTEKLA}", status_code=303)

        return await call_next(request)

app.add_middleware(AuthMiddleware)

# ── Zagon aplikacije (startup event) ────────────────────────────────────
# Ob zagonu:
# 1. Inicializiramo bazo (ustvari tabele, če ne obstajajo, + migracije)
# 2. Zaženemo večšolski bootstrap (app/tenancy.bootstrap_tenancy):
#      - privzeta šola (ostcj) z URL-aliasi
#      - glavni admin (main_admin) za upravljanje vseh šol
#      - šolski admin 'admin' pripada privzeti šoli
#      - obstoječi podatki (school_id IS NULL) se pripišejo privzeti šoli
#
# Zakaj bootstrap ob zagonu namesto seed skripte?
# Ker želimo, da aplikacija deluje 'out of the box' — ko se prvič
# zažene (lokalno ali v k8s), sta računa in šola že na voljo.
@app.on_event("startup")
def on_startup():
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        bootstrap_tenancy(db)
    finally:
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
def _render_index(request: Request, active_tab: str):
    """Skupna logika za prikaz glavne strani z izbranim zavihkom.

    active_tab: "rezervacije" ali "ocenjevanja" — pove front-endu, kateri
    zavihek naj bo aktiven ob nalaganju (glej ACTIVE_TAB v index.html).

    Timeout neaktivnosti pride iz nastavitev ŠOLE (school_settings), s
    fallbackom na .env — tako ga lahko šolski admin ureja v UI.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/auth/login")

    from app.database import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        config = config_for_request(request, db)
        # Ime šole, katere podatki so prikazani — uporabi se za oznako na vrhu.
        ctx_school_id, school = resolve_school_context(request, db)
        # Poti zavihkov: kdor je vstopil prek poti šole, na njej tudi ostane
        # (npr. iz /rezervacije_st klik na Ocenjevanje → /ocenjevanje_st).
        nav = nav_paths(db, request, ctx_school_id)
        # Glavni admin dobi spustni seznam šol (preklapljanje brez poti šole).
        nav_schools = []
        if user is not None and role_value(user) == MAIN_ADMIN_ROLE:
            from app.models import School
            nav_schools = [
                {"id": s.id, "name": s.name}
                for s in db.query(School).order_by(School.name).all()
            ]
    finally:
        db.close()

    # Admin/vodstvo (in glavni admin) imajo strožji timeout.
    is_privileged = user and role_value(user) in (RoleEnum.admin.value, RoleEnum.vodstvo.value, MAIN_ADMIN_ROLE)
    if is_privileged:
        timeout_ms = config.INACTIVITY_TIMEOUT_ADMIN_MINUTES * 60 * 1000
    else:
        timeout_ms = config.INACTIVITY_TIMEOUT_MINUTES * 60 * 1000

    # Označba šole: pokaže se VEDNO, ko je zahtevek prišel prek poti šole
    # (alias), da je uporabniku jasno, kateri šoli pripadajo podatki na zaslonu.
    return templates.TemplateResponse("index.html", {
        "request": request,
        "inactivity_timeout_ms": timeout_ms,
        "active_tab": active_tab,
        "school_alias": getattr(request.state, "school_alias", None),
        "school_name": school.name if school else None,
        "nav_rezervacije": nav.get("rezervacije", "/rezervacije"),
        "nav_ocenjevanje": nav.get("ocenjevanje", "/ocenjevanje"),
        "nav_schools": nav_schools,
        "current_school_id": ctx_school_id,
    })


# Korenska pot preusmeri na kanonični URL rezervacij.
@app.get("/")
def root(request: Request):
    return RedirectResponse(url="/rezervacije")


@app.get("/rezervacije")
def rezervacije_page(request: Request):
    """Glavna stran z aktivnim zavihkom Rezervacije."""
    return _render_index(request, "rezervacije")


@app.get("/ocenjevanje")
def ocenjevanje_page(request: Request):
    """Glavna stran z aktivnim zavihkom Ocenjevanje in dnevi dejavnosti."""
    return _render_index(request, "ocenjevanja")

# ── Preusmeritev admin uporabnikov ────────────────────────────────────
# Obstaja zaradi priročnosti — /admin/users se preusmeri na pravi endpoint.
@app.get("/admin/users")
def admin_users_redirect(request: Request):
    return RedirectResponse(url="/auth/admin/users")

# ── Javni API končne točke za konfiguracijo ──────────────────────────
# Te poti so javne (ni auth middleware-a), ker jih JavaScript v brskalniku
# kliče za prikaz padajočih menijev (razredi, prostori, urnik).
# Podatki niso občutljivi, so pa ODVISNI OD ŠOLE: če je uporabnik prijavljen,
# vrnemo nastavitve njegove šole; sicer (ali brez šole) privzete iz .env.
@app.get("/api/razredi")
def get_razredi(request: Request, db: Session = Depends(get_db)):
    return config_for_request(request, db).RAZREDI

@app.get("/api/prostori")
def get_prostori(request: Request, db: Session = Depends(get_db)):
    return config_for_request(request, db).PROSTORI

# Kateri prostori delujejo KOT TABLICE (več učiteljev hkrati, količina,
# omejitev na uro) in kolikšna je ta omejitev. Ločen endpoint, ker mora
# stran prilagoditi vnosna polja glede na nastavitve šole — prej je bilo
# to trdo zapisano ('tablice', 28).
@app.get("/api/prostori-qty")
def get_prostori_qty(request: Request, db: Session = Depends(get_db)):
    config = config_for_request(request, db)
    rooms = config.PROSTORI_QTY
    # Kapaciteta je lahko po prostoru različna (vsak prostor je vezan na svojo
    # številsko spremenljivko), zato vrnemo tudi zemljevid omejitev.
    limits = {room: config.kapaciteta(room) for room in rooms}
    return {"rooms": rooms, "max": config.TABLICE_MAX, "limits": limits}

@app.get("/api/schedule")
def get_schedule(request: Request, db: Session = Depends(get_db)):
    return config_for_request(request, db).SCHEDULE

# ── Zgodovina (audit log za admina) ──────────────────────────────────
# Prikaže HTML stran z audit logom, vendar samo če je prijavljeni
# uporabnik admin. Če ni, vrne 403 Forbidden.
#
# Zakaj posebna pot /history namesto /api/audit-log/page?
# Zgodovinska ujemanje — prejšnja verzija je uporabljala /history in
# uporabniki so se navadili. Oba endpointa obstajata.
@app.get("/ocenjevanje/dejavnosti", response_class=HTMLResponse)
def dejavnosti_page(request: Request):
    """Stran 'Vnos dejavnosti'. Branje: vsi prijavljeni. Urejanje: samo vodstvo/admin."""
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/auth/login")
    from app.database import SessionLocal
    db = SessionLocal()
    user = db.query(User).filter(User.id == int(user_id)).first()
    # Vloga gre v predlogo kot vrednost ('teacher'/'vodstvo'/'admin'), ne kot
    # str(RoleEnum) — sicer je učitelj dobil niz 'RoleEnum.teacher', primerjava
    # USER_ROLE !== 'teacher' pa je uspela in mu POKAZALA gumbe za urejanje
    # (klik je nato vrgel 403). Zdaj so gumbi učiteljem res skriti.
    role = role_value(user) if user else "teacher"
    # Poti zavihkov: kdor je vstopil prek poti šole, na njej tudi ostane.
    ctx_school_id, _school = resolve_school_context(request, db)
    nav = nav_paths(db, request, ctx_school_id)
    db.close()
    # Učitelji vseeno vidijo stran — gumbi za dodajanje/urejanje/brisanje
    # so jim skriti s pomočjo  USER_ROLE  v dejavnosti.html.
    return templates.TemplateResponse("dejavnosti.html", {
        "request": request,
        "user_role": role,
        "nav_rezervacije": nav.get("rezervacije", "/rezervacije"),
        "nav_ocenjevanje": nav.get("ocenjevanje", "/ocenjevanje"),
    })


@app.get("/dejavnosti")
def dejavnosti_redirect():
    """Stara pot — preusmeri na novo /ocenjevanje/dejavnosti (ohrani zaznamke)."""
    return RedirectResponse(url="/ocenjevanje/dejavnosti")


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    """Pokaži audit log — samo za prijavljenega admina (šolski ali glavni)."""
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/auth/login")
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user and role_value(user) in (RoleEnum.admin.value, MAIN_ADMIN_ROLE):
            # Glavni admin vidi vse; šolski admin samo uporabnike svoje šole.
            query = db.query(User.id, User.username, User.first_name, User.last_name)
            if not role_value(user) == MAIN_ADMIN_ROLE:
                query = query.filter(User.school_id == user.school_id)
            users = query.order_by(User.first_name).all()
            # Spustni seznam »Šola« (filtriranje dnevnika) ima samo glavni admin.
            from app.models import School
            from app.tenancy import is_main_admin
            main_admin = is_main_admin(user)
            schools = (
                [{"id": s.id, "name": s.name}
                 for s in db.query(School).order_by(School.name).all()]
                if main_admin else []
            )
            db.close()
            return templates.TemplateResponse("audit_log.html", {
                "request": request,
                "users": users,
                "is_main_admin": main_admin,
                "schools": schools,
            })
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
app.include_router(dejavnosti.router)
app.include_router(schools.router)
app.include_router(subscription.router)

# ── Statične datoteke za dokumentacijo ────────────────────────────────
# Slike iz dokumentacije (v /documentation/slike/) serviramo kot statične
# datoteke pod /slike/, da jih lahko HTML dokumentacija prikazuje.
# Če mapa ne obstaja (npr. v Docker sliki brez dokumentacije), ne mountamo.
# Static files: slike za dokumentacijo
import os
from app.security import get_current_user_id
slike_dir = os.path.join(os.path.dirname(__file__), "..", "documentation", "slike")
if os.path.exists(slike_dir):
    app.mount("/slike", StaticFiles(directory=slike_dir), name="slike")
