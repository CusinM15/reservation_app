# ─────────────────────────────────────────────────────────────────────────
# app/routers/govorilne.py — Prijave staršev na govorilne ure
#
# Namen: Javna stran /govorilne, kjer starš izbere učitelja in 15-minutni
# termin govorilnih ur (podatki o učiteljih/terminih v app/govorilne_podatki.py,
# vir: https://ostcjesenice.splet.arnes.si/za-starse/govorilne-ure/).
#
# Pravila:
#   - /govorilne in /govorilne/api/* so JAVNI (starši se ne prijavljajo).
#   - /govorilne/prijave je za prijavljene: učitelj vidi samo svoje prijave;
#     vodstvo, šolski admin in glavni admin vidijo vse prijave šole.
#   - En termin = 15 minut. Dopoldanski termini so TESTNI (testni teden),
#     popoldanski so uradni četrtki 17:30–18:30 iz spletne strani šole.
#   - Prijave se samodejno izbrišejo 14 dni po dnevu govorilnih ur (GDPR).
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GovorilnaPrijava
from app.tenancy import (
    _default_school_id,
    get_request_user,
    is_main_admin,
    is_school_admin,
    request_school_id,
    role_value,
)
from app.govorilne_podatki import (
    UCITELJI,
    POPOLDAN_DATUMI,
    URA_ZACETKI,
    GOVORILNE_DOPOLDAN_TEDEN,
)

router = APIRouter(tags=["govorilne"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Koliko minut traja en termin (zahteva uporabnika: 15 minut).
TERMIN_MINUT = 15
# Prijave se samodejno izbrišejo 24 ur po koncu termina govorilnih ur.
HRAMBA_UR = 24
# Termin je staršem viden največ 24 ur po začetku (starejši izginejo).
TERMIN_MAX_STAROST_UR = 24


# ═══════════════════════════════════════════════════════════════════════
# Pomožne funkcije — termini učitelja
# ═══════════════════════════════════════════════════════════════════════

def _ucitelj_by_ime(ime: str) -> dict | None:
    """Poišči učitelja po polnem imenu (case-insensitive, strpi se s presledki)."""
    needle = re.sub(r"\s+", " ", ime or "").strip().lower()
    for u in UCITELJI:
        if re.sub(r"\s+", " ", u["ime"]).lower() == needle:
            return u
    return None


def _add_minutes(hhmm: str, minutes: int) -> str:
    """"09:30" + 15 → "09:45" (24-urni zapis, samo navzgor)."""
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    t = (h * 60 + m + minutes) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


def _testni_datum(dan: int) -> date:
    """Dopoldanski (TESTNI) termin: testni teden + dan učitelja (0=pon..4=pet)."""
    return date.fromisoformat(GOVORILNE_DOPOLDAN_TEDEN) + timedelta(days=dan)


def _dopoldan_termini(u: dict) -> list[dict]:
    """Dopoldanski termini učitelja — 3 × 15 min znotraj njegove šolske ure.

    Če učitelj nima fiksnega termina (po_dogovoru → None dan/ura), nima
    dopoldanskih terminov — sprejema samo popoldan (uradni četrtki).
    """
    if u.get("po_dogovoru") or u.get("dan") is None or u.get("ura") is None:
        return []
    start = URA_ZACETKI.get(u["ura"])
    if not start:
        return []
    datum = _testni_datum(u["dan"])
    out = []
    for i in range(3):  # 45-min šolska ura → 3 × 15 min
        od = _add_minutes(start, i * TERMIN_MINUT)
        do = _add_minutes(od, TERMIN_MINUT)
        out.append({"datum": datum.isoformat(), "ura_od": od, "ura_do": do})
    return out


def _popoldan_termini() -> list[dict]:
    """Popoldanski termini — uradni četrtki 17:30–18:30 → 4 × 15 min.

    Veljajo za VSE učitelje (tudi tiste po dogovoru / brez dopoldanskega termina).
    """
    out = []
    for d in POPOLDAN_DATUMI:
        for i in range(4):  # 17:30–18:30 = 60 min → 4 × 15 min
            od = _add_minutes("17:30", i * TERMIN_MINUT)
            do = _add_minutes(od, TERMIN_MINUT)
            out.append({"datum": d, "ura_od": od, "ura_do": do})
    return out


def _naslednji_popoldan() -> str | None:
    """Prvi popoldanski datum (četrtek) >= danes — zgornja meja prikaza terminov."""
    danes = date.today().isoformat()
    return next((d for d in POPOLDAN_DATUMI if d >= danes), None)


def _konec_termina(p) -> datetime:
    """Konec termina prijave kot datetime (ura_do, sicer ura_od)."""
    ura = p.ura_do or p.ura_od or "00:00"
    h, m = map(int, ura.split(":")[:2])
    return datetime(p.datum.year, p.datum.month, p.datum.day, h, m)


def _prijava_pretekla(p) -> bool:
    """Ali je od konca termina minilo več kot HRAMBA_UR ur (→ avtomatski izbris)."""
    return _konec_termina(p) < datetime.now() - timedelta(hours=HRAMBA_UR)


def _v_oknu(t: dict) -> bool:
    """Ali je termin viden staršem: ni starejši od 24 ur in ni po naslednjih
    popoldanskih govorilnih (starejše/bolj oddaljene skrijemo)."""
    h, m = map(int, t["ura_od"].split(":"))
    d = date.fromisoformat(t["datum"])
    zacetek = datetime(d.year, d.month, d.day, h, m)
    if zacetek < datetime.now() - timedelta(hours=TERMIN_MAX_STAROST_UR):
        return False
    naslednji = _naslednji_popoldan()
    if naslednji is not None and t["datum"] > naslednji:
        return False
    return True


def _vsi_termini_ucitelja(u: dict) -> list[dict]:
    """Vsi termini učitelja (dopoldan + popoldan), ki so TRENUTNO VIDNI
    (okno: 24 ur nazaj → naslednje popoldanske govorilne), urejeni po datumu/uri."""
    terms = _dopoldan_termini(u) + _popoldan_termini()
    terms = [t for t in terms if _v_oknu(t)]
    terms.sort(key=lambda t: (t["datum"], t["ura_od"]))
    return terms


def _zasedeni_termini(db: Session, school_id: int | None, ucitelj: str) -> set[tuple]:
    """(datum, ura_od) pari, ki so že prijavljeni — da jih izpustimo iz ponudbe."""
    q = db.query(GovorilnaPrijava).filter(GovorilnaPrijava.ucitelj == ucitelj)
    if school_id is not None:
        q = q.filter(GovorilnaPrijava.school_id == school_id)
    return {(p.datum.isoformat(), p.ura_od) for p in q.all()}


def _prosti_termini(db: Session, school_id: int | None, ucitelj: dict) -> list[dict]:
    zauzeti = _zasedeni_termini(db, school_id, ucitelj["ime"])
    prosti = []
    for t in _vsi_termini_ucitelja(ucitelj):
        if (t["datum"], t["ura_od"]) not in zauzeti:
            prosti.append(t)
    return prosti


def _termini_z_flagom(db: Session, school_id: int | None, ucitelj: dict) -> list[dict]:
    """Vsi termini učitelja z bool ``zaseden`` (za javno stran staršev)."""
    zauzeti = _zasedeni_termini(db, school_id, ucitelj["ime"])
    termini = []
    for t in _vsi_termini_ucitelja(ucitelj):
        vnos = dict(t)
        vnos["zaseden"] = (t["datum"], t["ura_od"]) in zauzeti
        termini.append(vnos)
    return termini


def _termin_obstaja(ucitelj: dict, datum: str, ura_od: str) -> bool:
    """Ali je (datum, ura_od) en izmed veljavnih terminov tega učitelja?"""
    return any(t["datum"] == datum and t["ura_od"] == ura_od
               for t in _vsi_termini_ucitelja(ucitelj))


# ═══════════════════════════════════════════════════════════════════════
# Javna stran — prijava starša
# ═══════════════════════════════════════════════════════════════════════

@router.get("/govorilne", response_class=HTMLResponse)
def govorilne_stran(request: Request, db: Session = Depends(get_db)):
    """Javna prijavna stran: izbor učitelja, nato 15-minutni termini."""
    school_id = _default_school_id(db)
    ucitelji = sorted(
        [{"ime": u["ime"], "predmet": u["predmet"], "prostor": u["prostor"]}
         for u in UCITELJI],
        key=lambda x: x["ime"].lower(),
    )
    return templates.TemplateResponse(
        request, "govorilne.html",
        {"ucitelji": ucitelji, "termin_minut": TERMIN_MINUT,
         "hramba_ur": HRAMBA_UR},
    )


@router.get("/govorilne/api/termini")
def govorilne_termini(
    ucitelj: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Prosti termini izbranega učitelja (JSON) — za dinamični UI."""
    u = _ucitelj_by_ime(ucitelj)
    if u is None:
        raise HTTPException(status_code=404, detail="Učitelj ne obstaja")
    school_id = request_school_id(request) or _default_school_id(db)
    return {"ucitelj": u["ime"], "termini": _termini_z_flagom(db, school_id, u)}


@router.post("/govorilne/api/prijava")
async def govorilne_prijava(
    request: Request,
    db: Session = Depends(get_db),
):
    """Shrani prijavo starša. Termin mora biti veljaven in prost (409 sicer)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    ucitelj_ime = (body.get("ucitelj") or "").strip()
    datum = (body.get("datum") or "").strip()
    ura_od = (body.get("ura_od") or "").strip()
    ura_do = (body.get("ura_do") or "").strip()
    ime_starsa = (body.get("ime_starsa") or "").strip()
    email = (body.get("email") or "").strip()
    otrok = (body.get("otrok") or "").strip()

    u = _ucitelj_by_ime(ucitelj_ime)
    if u is None:
        raise HTTPException(status_code=400, detail="Neznan učitelj")
    if not ime_starsa or not email or not otrok:
        raise HTTPException(status_code=400, detail="Izpolnite ime starša, e-naslov in ime otroka")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="E-naslov ni veljaven")
    if not _termin_obstaja(u, datum, ura_od):
        raise HTTPException(status_code=400, detail="Termin ne obstaja za tega učitelja")

    school_id = request_school_id(request) or _default_school_id(db) or 1

    # Prepreči dvojno prijavo istega termina (tudi ob sočasnih zahtevkih —
    # UniqueConstraint v bazi; tu najprej prijazno preverimo).
    existing = db.query(GovorilnaPrijava).filter(
        GovorilnaPrijava.school_id == school_id,
        GovorilnaPrijava.ucitelj == u["ime"],
        GovorilnaPrijava.datum == date.fromisoformat(datum),
        GovorilnaPrijava.ura_od == ura_od,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ta termin je že zaseden")

    prijava = GovorilnaPrijava(
        school_id=school_id,
        ucitelj=u["ime"],
        datum=date.fromisoformat(datum),
        ura_od=ura_od,
        ura_do=ura_do,
        ime_starsa=ime_starsa,
        email=email,
        otrok=otrok,
    )
    db.add(prijava)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ta termin je že zaseden")

    return {"ok": True, "sporocilo": "Prijava je uspela."}


# ═══════════════════════════════════════════════════════════════════════
# Pregled prijav — samo za prijavljene (učitelj svoje, vodstvo/admin vse)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/govorilne/prijave", response_class=HTMLResponse)
def govorilne_prijave_stran(request: Request, db: Session = Depends(get_db)):
    user = get_request_user(request, db)
    if user is None:
        return RedirectResponse(url="/auth/login")

    role = role_value(user)
    q = db.query(GovorilnaPrijava)
    if is_main_admin(user):
        pass  # glavni admin vidi vse šole
    else:
        q = q.filter(GovorilnaPrijava.school_id == (user.school_id or _default_school_id(db)))
        if role == "teacher":
            polno_ime = f"{user.first_name} {user.last_name}".strip()
            q = q.filter(GovorilnaPrijava.ucitelj == polno_ime)

    prijave = q.order_by(GovorilnaPrijava.datum.desc(),
                         GovorilnaPrijava.ura_od).all()

    # GDPR: prijave se izbrišejo 24 ur po koncu termina — pretekle
    # ne prikazujemo več (v ozadju se tudi pobrišejo).
    _pocisti_stare(db)
    prijave = [p for p in prijave if not _prijava_pretekla(p)]

    return templates.TemplateResponse(
        request, "govorilne_prijave.html",
        {"prijave": prijave, "role": role, "is_teacher": role == "teacher"},
    )


def _pocisti_stare(db: Session) -> int:
    """Izbriši prijave, od katerih je minilo več kot HRAMBA_UR ur (24 ur po dogodku)."""
    starih = [p for p in db.query(GovorilnaPrijava).all() if _prijava_pretekla(p)]
    if starih:
        for p in starih:
            db.delete(p)
        db.commit()
    return len(starih)


# ═══════════════════════════════════════════════════════════════════════
# »Moje govorilne ure« — učitelj v appu vidi svoj objavljeni urnik
# ═══════════════════════════════════════════════════════════════════════

# Dnevi v tednu (0=pon..4=pet) za prikaz govorilnih ur.
_DANI = ["ponedeljek", "torek", "sreda", "četrtek", "petek"]


def _urnik_ucitelja(db: Session, school_id: int | None, u: dict) -> dict:
    """Pripravi prikaz objavljenega urnika govorilnih ur enega učitelja
    (dopoldanski + popoldanski termin) skupaj z rezervacijami staršev."""
    dopoldan = None
    if not u.get("po_dogovoru") and u.get("dan") is not None and u.get("ura") is not None:
        dan = _DANI[u["dan"]] if 0 <= u["dan"] < 5 else f"dan {u['dan']}"
        dopoldan = {
            "dan": dan,
            "ura": u["ura"],
            "zacetek": URA_ZACETKI.get(u["ura"]),
            "datum": _testni_datum(u["dan"]).isoformat(),
        }
    q = db.query(GovorilnaPrijava).filter(
        GovorilnaPrijava.ucitelj == u["ime"],
        # Širši kos (včerajšnji datum): natančno izločimo pretekle v Pythonu.
        GovorilnaPrijava.datum >= date.today() - timedelta(days=1),
    )
    if school_id is not None:
        q = q.filter(GovorilnaPrijava.school_id == school_id)
    rezervacije = [p for p in q.order_by(GovorilnaPrijava.datum,
                                         GovorilnaPrijava.ura_od).all()
                   if not _prijava_pretekla(p)]
    naslednji = _naslednji_popoldan()
    return {
        "ime": u["ime"],
        "predmet": u["predmet"],
        "prostor": u["prostor"],
        "po_dogovoru": bool(u.get("po_dogovoru")),
        "dopoldan": dopoldan,
        # Samo AKTUALNE popoldanske govorilne (naslednji četrtek) — ne celo leto.
        "popoldan_datumi": [naslednji] if naslednji else [],
        "rezervacije": rezervacije,
    }


@router.get("/govorilne/ure", response_class=HTMLResponse)
def govorilne_ure_stran(request: Request, db: Session = Depends(get_db)):
    """Učitelj v appu vidi svoj objavljeni urnik govorilnih ur in rezervacije.

    - Učitelj: samo svoj objavljeni termin (dan/uro/prostor + termin za prijave).
    - Vodstvo, šolski admin, glavni admin: pregled urnikov vseh učiteljev.
    """
    user = get_request_user(request, db)
    if user is None:
        return RedirectResponse(url="/auth/login")

    role = role_value(user)
    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id

    if role == "teacher":
        polno_ime = f"{user.first_name} {user.last_name}".strip()
        ucitelj = _ucitelj_by_ime(polno_ime)
        prikaz = [_urnik_ucitelja(db, school_id, ucitelj)] if ucitelj else []
    else:
        prikaz = [_urnik_ucitelja(db, school_id, u) for u in UCITELJI]

    return templates.TemplateResponse(
        request, "govorilne_ure.html",
        {"prikaz": prikaz, "role": role, "is_teacher": role == "teacher"},
    )
