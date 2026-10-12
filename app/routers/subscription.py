# ─────────────────────────────────────────────────────────────────────────
# app/routers/subscription.py — naročnine: status, nakup, potrditev plačila
#
# Namen: šola vidi stanje svoje naročnine in kupi nov mesec; glavni admin
# potrjuje prejeta plačila (naročnina se podaljša za en mesec) in ureja
# nastavitve prodaje (cena, PayPal povezava).
#
# Varnost: podatkov o kartici tu NI — plačilo poteka na PayPalovi strani,
# v bazi je le evidenca (znesek, sklic, opomba, kdo je potrdil).
# ─────────────────────────────────────────────────────────────────────────

import secrets
from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.templating import make_templates
from app.i18n import current_lang
from sqlalchemy.orm import Session

from app.app_settings import (
    plan_by_id,
    prorated_price_eur,
    save_selling_config,
    selling_config,
    subscription_period_end,
)
from app.audit import log_audit
from app.config import validate_password_strength
from app.database import get_db
from app.models import Payment, RoleEnum, School, User
from app.routers.auth import get_password_hash
from app.routers.schools import _manageable_school
from app.security import sign_user_id
from app.subscriptions import (
    auto_renew_enabled,
    extend_subscription,
    extend_to_school_year,
    next_charge_day,
    school_year_target,
    self_extend_open,
    set_auto_renew,
    subscription_state,
)
from app.security import inactivity_timeout_ms
from app.tenancy import (
    apply_test_email_settings,
    create_school,
    default_school_admin_username,
    get_request_user,
    is_main_admin,
    school_admin_username_from_initials,
    slugify,
)

router = APIRouter(tags=["narocnina"])
templates = make_templates()


def _require_main_admin(db: Session, request: Request):
    """Samo glavni admin sme potrjevati plačila in urejati prodajo."""
    user = get_request_user(request, db)
    if user is None or not is_main_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Plačila in nastavitve prodaje lahko ureja le glavni admin.",
        )
    return user


def _parse_iso_date(value: str | None) -> date | None:
    """Pretvori »YYYY-MM-DD« v date; neveljavno/prazno → None."""
    text = (value or "").strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/nakup", response_class=HTMLResponse)
def nakup_page(
    request: Request,
    start: str | None = None,
    db: Session = Depends(get_db),
):
    """JAVNA stran za nakup naročnine (brez prijave).

    Zakaj javna? Gumb »Nakup / podaljšanje naročnine« je na prijavni strani, kjer
    uporabnik še NI prijavljen. Če bi ta gumb kazal na /narocnina (zaščiteno),
    bi middleware obiskovalca takoj vrnil na prijavo — uporabniku se zdi, da klik
    ne naredi nič. Zato je ponudba javna, stanje in sporočanje plačila pa ostaneta
    za prijavljene (šolski/glavni admin).

    Če je cena > 0, lahko šola izbere datum začetka; cena je SORAZMERNA do 1. 9.
    (glej prorated_price_eur), zato npr. začetek 1. 3. pri polni ceni 12 € znaša ~6 €.
    """
    cfg = selling_config(db)
    izbrani_start = _parse_iso_date(start) or date.today()
    return templates.TemplateResponse(
        "nakup.html",
        {
            "request": request,
            "cfg": cfg,
            "start": izbrani_start,
            "period_end": subscription_period_end(izbrani_start),
            "prorated": prorated_price_eur(db, izbrani_start),
        },
    )


@router.get("/registracija", response_class=HTMLResponse)
def registracija_page(
    request: Request,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """JAVNA stran: nova šola si ustvari račun (pred plačilom naročnine).

    Zakaj javno? Na prijavni strani mora nova šola imeti kam klikniti, še preden
    ima kakršen koli račun. Ustvarjena šola je takoj uporabna, a ker nima
    naročnine, se učitelji ne morejo prijaviti, dokler administrator šole
    naročnine ne uredi in je ne potrdimo.
    """
    cfg = selling_config(db)
    if not cfg["enabled"]:
        # Brez prodaje ni registracije (namestitev v šoli tega ne potrebuje).
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        "registracija.html",
        {"request": request, "cfg": cfg, "error": error},
    )


def _generirano_geslo(dolzina: int = 12) -> str:
    """Sestavi naključno geslo, ki ustreza pravilom šole.

    Znake, ki se radi zamešajo (O/0, l/1), namenoma izpustimo — geslo bo
    uporabnik prepisoval z zaslona. Pravila (male/velike črke + številka)
    zagotovimo z zanko, da je rezultat vedno veljaven.
    """
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        kandidat = "".join(secrets.choice(alphabet) for _ in range(dolzina))
        if validate_password_strength(kandidat) is None:
            return kandidat
    # Sem pridemo le teoretično; dodamo vsiljeno številko in veliko črko.
    return "".join(secrets.choice(alphabet) for _ in range(dolzina - 2)) + "9K"


def _prost_slug(db: Session, osnova: str) -> str:
    """Vrni prosto kratico šole; ob zasedenosti doda -2, -3 ...

    Zakaj? Kratico naredimo samodejno iz imena šole, zato ob morebitnem
    podvajanju (npr. dve »Osnovna šola«) uporabnika ne ustavimo z napako,
    ampak mu dodelimo prosto različico.
    """
    osnova = osnova or "sola"
    kandidat = osnova
    stevec = 2
    while db.query(School).filter(School.slug == kandidat).first():
        kandidat = f"{osnova}-{stevec}"
        stevec += 1
    return kandidat


def _prosto_uporabnisko_ime(db: Session, osnova: str) -> str:
    """Vrni prosto uporabniško ime; ob zasedenosti doda 2, 3 ...

    Uporabniška imena so v bazi unikatna po šoli, prijava pa išče po celem
    sistemu (brez poti šole) — zato mora biti ime prosto tudi globalno.
    """
    kandidat = osnova
    stevec = 2
    while db.query(User).filter(User.username == kandidat).first():
        kandidat = f"{osnova}{stevec}"
        stevec += 1
    return kandidat


@router.post("/registracija")
def registracija_submit(
    request: Request,
    name: str = Form(""),
    lang: str = Form(""),
    db: Session = Depends(get_db),
):
    """Ustvari novo šolo; administratorja določimo SAMODEJNO.

    Zakaj tako? Uporabnik pri registraciji vpiše le šolo — kratico, uporabniško
    ime in geslo administratorja določimo mi (kratico iz imena, uporabniško ime
    `admin_<kratica>`, geslo naključno). Geslo pokažemo enkrat po ustvarjanju,
    pozneje pa ga lahko uporabnik spremeni v aplikaciji.
    """
    cfg = selling_config(db)
    if not cfg["enabled"]:
        raise HTTPException(status_code=403, detail="Registracija v tej namestitvi ni mogoča.")

    def napaka(sporocilo: str):
        return templates.TemplateResponse(
            "registracija.html",
            {"request": request, "cfg": cfg, "error": sporocilo, "name": name},
            status_code=400,
        )

    name = (name or "").strip()
    if len(name) < 3:
        return napaka("Vpišite polno ime šole (najmanj 3 znake).")

    slug = _prost_slug(db, slugify(name))
    # Uporabniško ime admina = admin_<inicialke imena šole> (npr. admin_ost);
    # če inicialk ni mogoče sestaviti, uporabimo oznako šole. Ob zasedenosti
    # dodamo številko.
    osnova_imena = school_admin_username_from_initials(name) or default_school_admin_username(slug)
    username = _prosto_uporabnisko_ime(db, osnova_imena)
    geslo = _generirano_geslo()

    # Jezik vmesnika nove šole: iz povezave »Nova šola« (sl) oziroma
    # »New school« (en); če ni podan, uporabimo jezik trenutne zahteve.
    _lang = (lang or request.query_params.get("lang") or "").strip().lower()[:2]
    if _lang not in ("sl", "en"):
        _lang = current_lang() or "sl"

    try:
        school = create_school(db, name=name, slug=slug, ui_language=_lang)
    except ValueError as exc:
        return napaka(str(exc))

    # E-pošta: nova šola dobi TESTNE naslove (namesto naših iz .env) — admin jih
    # zamenja v Nastavitvah šole, sicer bi pošta šla z napačnim pošiljateljem.
    apply_test_email_settings(db, school.id)

    admin = User(
        school_id=school.id,
        username=username,
        email=None,
        first_name="Administrator",
        last_name="",
        password_hash=get_password_hash(geslo),
        role=RoleEnum.admin,
    )
    db.add(admin)
    db.commit()

    log_audit(
        db, admin.id, admin.username, "register_school",
        f"school_id={school.id}, slug={school.slug}, name={school.name}, "
        f"cena={cfg['price_label']}, admin={username} (geslo generirano)",
        school_id=school.id,
    )

    # Prijavimo administratorja in pokažemo ustvarjene podatke (geslo se prikaže
    # samo enkrat — zato stran, ne preusmeritev, da geslo ne pride v naslov).
    response = templates.TemplateResponse(
        "registracija_uspeh.html",
        {
            "request": request,
            "cfg": cfg,
            "school": school,
            "username": username,
            "geslo": geslo,
        },
    )
    response.set_cookie(key="user_id", value=sign_user_id(admin.id), httponly=True, samesite="lax")
    response.set_cookie(key="role", value=admin.role, httponly=True, samesite="lax")
    # Šola novega admina — brez tega bi v brskalniku ostala izbira PREJŠNJE šole
    # in vsaka zahteva bi se končala z »Nimate dostopa do podatkov te šole.«
    response.set_cookie(key="school_ctx", value=str(school.id), httponly=True, samesite="lax")
    return response


@router.post("/narocnina/avto")
def toggle_auto_renew(
    request: Request,
    auto: str = Form("0"),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Vklop/izklop samodejnega plačila za šolo (šolski ali glavni admin)."""
    school = _manageable_school(db, request, school_id)
    user = get_request_user(request, db)
    set_auto_renew(db, school.id, str(auto) == "1")
    db.commit()
    log_audit(
        db, user.id if user else None, user.username if user else "?",
        "toggle_auto_renew",
        f"school_id={school.id}, avtomatsko={'vklopljeno' if str(auto) == '1' else 'izklopljeno'}",
        school_id=school.id,
    )
    stanje = "vklopljeno" if str(auto) == "1" else "izklopljeno"
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info=Samodejno plačilo je {stanje}.",
        status_code=303,
    )


@router.get("/narocnina", response_class=HTMLResponse)
def narocnina_page(
    request: Request,
    school_id: int | None = None,
    info: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Stanje naročnine + nakup za izbrano šolo (šolski ali glavni admin)."""
    # Učitelja sem preusmeri middleware, ko naročnina poteče — takrat naj vidi
    # le obvestilo (kupuje lahko samo administrator šole), ne pa napake 403.
    view_only = False
    try:
        school = _manageable_school(db, request, school_id)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        user0 = get_request_user(request, db)
        school = db.query(School).filter(School.id == (user0.school_id if user0 else None)).first()
        if school is None:
            raise
        view_only = True

    user = get_request_user(request, db)

    payments = (
        db.query(Payment)
        .filter(Payment.school_id == school.id)
        .order_by(Payment.reported_at.desc())
        .limit(10)
        .all()
    )

    # Glavni admin vidi tudi vsa nerešena plačila po vseh šolah.
    pending: list[dict] = []
    if is_main_admin(user):
        rows = (
            db.query(Payment, School)
            .join(School, Payment.school_id == School.id)
            .filter(Payment.status == "pending")
            .order_by(Payment.reported_at)
            .all()
        )
        pending = [
            {
                "id": p.id,
                "school_name": s.name,
                "school_id": s.id,
                "amount_eur": p.amount_eur,
                "reference": p.reference,
                "note": p.note,
                "reported_at": p.reported_at,
            }
            for p, s in rows
        ]

    return templates.TemplateResponse(
            "narocnina.html",
            {
                "request": request,
                "inactivity_timeout_ms": inactivity_timeout_ms(user),
                "school": school,
            "state": subscription_state(db, school.id),
            "cfg": selling_config(db),
            "payments": payments,
            "pending": pending,
            "is_main_admin": is_main_admin(user),
            "is_admin": bool(user and user.role in (RoleEnum.admin, RoleEnum.main_admin)),
            "extend_open": self_extend_open(),
            "extend_until": school_year_target(),
            "view_only": view_only,
            "avto": auto_renew_enabled(db, school.id),
            "dan_obnove": next_charge_day(db, school.id),
            "user": user,
            "info": info,
            "error": error,
            "danes": datetime.now(),
        },
    )


@router.post("/narocnina/sporoci-placilo")
def report_payment(
    request: Request,
    reference: str = Form(""),
    note: str = Form(""),
    plan: str = Form("leto"),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Šola sporoči, da je plačala (plan: leto).

    Znesek in število mesecev se določita iz izbranega plana; glavni admin nato
    potrdi in podaljša naročnino za toliko mesecev.
    """
    school = _manageable_school(db, request, school_id)
    user = get_request_user(request, db)
    izbrani = plan_by_id(db, plan) or plan_by_id(db, "leto")

    db.add(Payment(
        school_id=school.id,
        amount_eur=izbrani["price"],
        months=izbrani["months"],
        reference=(reference or "").strip(),
        note=(note or "").strip(),
        status="pending",
        reported_by_id=user.id if user else None,
    ))
    db.commit()
    log_audit(
        db, user.id if user else None, user.username if user else "?",
        "report_payment",
        f"school_id={school.id}, znesek={izbrani['price']} EUR, "
        f"plan={izbrani['id']} ({izbrani['months']} mes.), sklic={reference}",
        school_id=school.id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info=Plačilo je zabeleženo. "
            f"Ko bo nakazilo prejeto, bo naročnina podaljšana za {izbrani['label']} "
            f"({izbrani['months']} mes.).",
        status_code=303,
    )


@router.post("/narocnina/potrdi/{payment_id}")
def confirm_payment(
    payment_id: int,
    request: Request,
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Glavni admin potrdi prejeto plačilo → naročnina velja do 1. 9. naslednje leto."""
    user = _require_main_admin(db, request)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Plačilo ne obstaja.")

    until = extend_to_school_year(db, payment.school_id)
    payment.status = "confirmed"
    payment.valid_until = until
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by = user.username
    db.commit()
    log_audit(
        db, user.id, user.username, "confirm_payment",
        f"payment_id={payment.id}, school_id={payment.school_id}, "
        f"znesek={payment.amount_eur} EUR, veljavnost do {until.isoformat()}",
        school_id=payment.school_id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={payment.school_id}&info="
            f"Plačilo potrjeno — naročnina velja do {until.day}. {until.month}. {until.year}.",
        status_code=303,
    )


@router.post("/narocnina/zavrni/{payment_id}")
def reject_payment(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Glavni admin zavrne sporočeno plačilo (npr. nakazilo ni prispelo)."""
    user = _require_main_admin(db, request)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Plačilo ne obstaja.")
    payment.status = "rejected"
    payment.confirmed_at = datetime.utcnow()
    payment.confirmed_by = user.username
    db.commit()
    log_audit(
        db, user.id, user.username, "reject_payment",
        f"payment_id={payment.id}, school_id={payment.school_id}",
        school_id=payment.school_id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={payment.school_id}&info=Plačilo je označeno kot neprejeto.",
        status_code=303,
    )


@router.post("/narocnina/podaljsaj")
def grant_months(
    request: Request,
    months: int | None = Form(None),
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Glavni admin podaljša naročnino brez plačila (npr. za svojo šolo).

    Veljavnost se VEDNO nastavi na 1. 9. naslednje leto (enotno za vse šole) —
    ne glede na morebitno poslano število mesecev.
    """
    user = _require_main_admin(db, request)
    school = _manageable_school(db, request, school_id)
    until = extend_to_school_year(db, school.id)
    db.commit()
    log_audit(
        db, user.id, user.username, "grant_subscription",
        f"school_id={school.id}, veljavnost do {until.isoformat()} (1. 9. naslednje leto)",
        school_id=school.id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info="
            f"Naročnina podaljšana do {until.day}. {until.month}. {until.year}.",
        status_code=303,
    )


@router.post("/narocnina/podaljsaj-sola")
def extend_school_year_self(
    request: Request,
    school_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Šolski admin (ali glavni admin) SAM podaljša naročnino svoje šole.

    Veljavnost se nastavi na **1. 9. naslednje leto** (celo šolsko leto naprej).
    Dovoljeno je **od 15. 8. dalje**; zunaj tega okna vrne opozorilo in ne spremeni
    ničesar.
    """
    user = get_request_user(request, db)
    if user is None or user.role not in (RoleEnum.admin, RoleEnum.main_admin):
        raise HTTPException(
            status_code=403,
            detail="Naročnino lahko podaljša le administrator šole.",
        )
    school = _manageable_school(db, request, school_id)

    if not self_extend_open():
        target = school_year_target()
        return RedirectResponse(
            url=f"/narocnina?school_id={school.id}&error="
                f"Podaljšanje naročnine je mogoče šele od 15. 8. "
                f"(do {target.day}. {target.month}. {target.year}).",
            status_code=303,
        )

    until = extend_to_school_year(db, school.id)
    db.commit()
    log_audit(
        db, user.id, user.username, "extend_subscription_school_year",
        f"school_id={school.id}, veljavnost do {until.isoformat()} "
        f"(samopostrežno, 1. 9. naslednje leto)",
        school_id=school.id,
    )
    return RedirectResponse(
        url=f"/narocnina?school_id={school.id}&info="
            f"Naročnina podaljšana do {until.day}. {until.month}. {until.year}.",
        status_code=303,
    )


@router.post("/narocnina/nastavitve")
def save_settings(
    request: Request,
    selling: str = Form("0"),
    price_eur: str = Form("13"),
    paypal_url: str = Form(""),
    paypal_sub_url: str = Form(""),
    payment_note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Glavni admin shrani nastavitve prodaje (cena letnega plana, PayPal, navodila)."""
    user = _require_main_admin(db, request)
    save_selling_config(
        db,
        enabled=(str(selling) == "1"),
        price=price_eur,
        paypal=paypal_url,
        paypal_sub=paypal_sub_url,
        note=payment_note,
    )
    db.commit()
    log_audit(
        db, user.id, user.username, "save_selling_settings",
        f"prodaja={'vklopljena' if str(selling) == '1' else 'izklopljena'}, "
        f"cena_leto={price_eur} EUR, "
        f"paypal={'nastavljen' if paypal_url else 'prazen'}, "
        f"samodejni paypal={'nastavljen' if paypal_sub_url else 'prazen'}",
        school_id=None,
    )
    return RedirectResponse(
        url="/narocnina?info=Nastavitve prodaje so shranjene.", status_code=303
    )
