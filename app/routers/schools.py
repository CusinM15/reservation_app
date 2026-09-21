# ─────────────────────────────────────────────────────────────────────────
# app/routers/schools.py — Upravljanje šol (tenantov) in nastavitev šole
#
# Namen:
#   * GLAVNI ADMIN (main_admin): pregled vseh šol, ustvarjanje nove šole,
#     urejanje nastavitev katere koli šole, odpiranje posamezne šole.
#   * ŠOLSKI ADMIN (admin): urejanje nastavitev SVOJE šole.
#
# Zakaj ločen router? Večšolska logika je svoja domena — uporabniki jo
# potrebujejo neodvisno od rezervacij/ocenjevanj. Tako ostanejo drugi
# routerji osredotočeni na svojo domeno.
#
# Pravice (trdna meja):
#   - main_admin vidi vse šole in vse podatke.
#   - admin (šolski) vidi izključno svojo šolo.
#   - vodstvo/teacher ne vidita teh strani (403).
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import School, SchoolAlias, User, Reservation, Assessment, ActivityDay, RoleEnum
from app.audit import log_audit
from app.security import get_current_user_id
from app.tenancy import (
    ASSESSMENT_RULE_DEFAULTS,
    MAIN_ADMIN_ROLE,
    SCHOOL_ADMIN_ROLE,
    SCHOOL_SETTING_FIELDS,
    SCHOOL_SETTING_KEYS,
    add_school_alias,
    create_school,
    generate_aliases,
    get_request_user,
    invalidate_alias_cache,
    is_main_admin,
    is_school_admin,
    request_school_id,
    role_value,
    set_school_setting,
    get_school_config,
    slugify,
)

router = APIRouter(tags=["schools"])
templates = Jinja2Templates(directory="app/templates")

# Vloge, ki smejo urejati nastavitve svoje šole
_SETTINGS_AUDIT_ACTION = "update_school_settings"


# ── Pomožne funkcije za pravice ────────────────────────────────────────

def _require_login(request: Request, db: Session) -> User:
    """Vrni prijavljenega uporabnika ali dvigni 401."""
    user = get_request_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    return user


def _require_main_admin(request: Request, db: Session) -> User:
    user = _require_login(request, db)
    if not is_main_admin(user):
        raise HTTPException(status_code=403, detail="Dostop samo za glavnega admina")
    return user


def _manageable_school(db: Session, request: Request, school_id: int | None = None) -> School:
    """Vrni šolo, ki jo uporabnik sme upravljati.

    Glavni admin: poljubno šolo (podana, iz URL-aliasa ali edina obstoječa).
    Šolski admin: izključno svojo šolo.
    """
    user = _require_login(request, db)

    if is_main_admin(user):
        sid = school_id or request_school_id(request)
        if sid is None:
            all_schools = db.query(School).order_by(School.id).all()
            if len(all_schools) == 1:
                return all_schools[0]
            raise HTTPException(
                status_code=400,
                detail="Izberite šolo (parameter school_id ali pot šole).",
            )
        school = db.query(School).filter(School.id == sid).first()
        if not school:
            raise HTTPException(status_code=404, detail="Šola ne obstaja")
        return school

    if not is_school_admin(user):
        raise HTTPException(status_code=403, detail="Nastavitve šole lahko ureja samo šolski admin")
    if not user.school_id:
        raise HTTPException(status_code=400, detail="Vaš račun ni vezan na nobeno šolo")
    # Če je zahtevek naslovljen na DRUGO šolo, ga zavrnemo. Brez tega bi
    # šolski admin lahko poslal school_id=2 in bi se sprememba tiho zapisala
    # v NJEGOVO šolo (1) — klicatelj pa bi mislil, da je uredil šolo 2.
    if school_id is not None and int(school_id) != int(user.school_id):
        raise HTTPException(status_code=403, detail="Nastavitve lahko urejate samo za svojo šolo.")
    school = db.query(School).filter(School.id == user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Šola ne obstaja")
    return school


def _school_counts(db: Session, school_id: int) -> dict:
    """Osnovna statistika šole (za pregled glavnega admina)."""
    return {
        "users": db.query(User).filter(User.school_id == school_id).count(),
        "reservations": db.query(Reservation).filter(Reservation.school_id == school_id).count(),
        "assessments": db.query(Assessment).filter(Assessment.school_id == school_id).count(),
        "activities": db.query(ActivityDay).filter(ActivityDay.school_id == school_id).count(),
    }


# ═══════════════════════════════════════════════════════════════════════
# API — glavni admin: šole
# ═══════════════════════════════════════════════════════════════════════

@router.get("/api/schools")
def list_schools(request: Request, db: Session = Depends(get_db)):
    """Seznam vseh šol s statistiko (samo glavni admin)."""
    _require_main_admin(request, db)
    rows = db.query(School).order_by(School.id).all()
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "is_active": s.is_active,
            "aliases": [a.alias for a in s.aliases],
            "counts": _school_counts(db, s.id),
        }
        for s in rows
    ]


@router.get("/api/schools/current")
def current_school(request: Request, db: Session = Depends(get_db)):
    """Vrni šolo trenutnega zahtevka (iz URL-aliasa ali uporabnikove šole)."""
    user = _require_login(request, db)
    school_id = request_school_id(request) or user.school_id
    if school_id is None:
        return {"school": None, "role": role_value(user)}
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        return {"school": None, "role": role_value(user)}
    return {
        "school": {"id": school.id, "slug": school.slug, "name": school.name,
                   "aliases": [a.alias for a in school.aliases]},
        "role": role_value(user),
    }


@router.post("/api/schools", status_code=201)
def create_new_school(
    request: Request,
    name: str = Form(...),
    slug: str = Form(""),
    db: Session = Depends(get_db),
):
    """Ustvari novo šolo (samo glavni admin).

    Aliasi se generirajo iz sluga (npr. "xyz" → /rezervacije_xyz in
    /ocenjevanje_xyz), nastavitve pa se napolnijo iz privzetih vrednosti
    (.env), da nova šola takoj deluje in jih šolski admin nato uredi.
    """
    admin = _require_main_admin(request, db)
    try:
        school = create_school(db, name=name, slug=slug or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_audit(db, admin.id, admin.username, "create_school",
              f"school_id={school.id}, slug={school.slug}, name={school.name}")
    return {
        "id": school.id,
        "slug": school.slug,
        "name": school.name,
        "aliases": [a.alias for a in school.aliases],
    }


@router.post("/api/schools/{school_id}/aliases", status_code=201)
def create_school_alias(
    school_id: int,
    request: Request,
    alias: str = Form(...),
    db: Session = Depends(get_db),
):
    """Dodaj URL-alias šoli (glavni admin ali šolski admin svoje šole)."""
    school = _manageable_school(db, request, school_id)
    try:
        row = add_school_alias(db, school.id, alias)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": row.id, "alias": row.alias, "kind": row.kind}


# ═══════════════════════════════════════════════════════════════════════
# API — nastavitve šole
# ═══════════════════════════════════════════════════════════════════════

def _settings_payload(db: Session, school: School) -> dict:
    """Nastavitve šole (dejanske vrednosti) + opis polj za UI."""
    config = get_school_config(db, school.id)
    return {
        "school": {"id": school.id, "slug": school.slug, "name": school.name,
                   "aliases": [a.alias for a in school.aliases]},
        "values": config.effective_values(),
        "fields": SCHOOL_SETTING_FIELDS,
        "assessment_defaults": ASSESSMENT_RULE_DEFAULTS,
    }


@router.get("/api/schools/{school_id}/settings")
def get_school_settings(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Vrni nastavitve šole (glavni admin poljubne, šolski admin svoje)."""
    school = _manageable_school(db, request, school_id)
    return _settings_payload(db, school)


@router.put("/api/schools/{school_id}/settings")
async def update_school_settings(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Posodobi nastavitve šole.

    Telo zahtevka: {"values": {"KLJUČ": "vrednost", ...}}
    Sprejemamo samo znane ključe (SCHOOL_SETTING_KEYS), da ne moremo
    v bazo zapisati poljubnih nastavitev.
    """
    school = _manageable_school(db, request, school_id)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")
    values = body.get("values") if isinstance(body, dict) else None
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Manjka 'values' (slovar nastavitev)")

    unknown = [k for k in values if k not in SCHOOL_SETTING_KEYS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Neznane nastavitve: {', '.join(sorted(unknown))}")

    # Preprosta validacija tipov: int polja morajo biti cela števila,
    # SCHEDULE mora biti veljaven JSON.
    import json as _json
    for field in SCHOOL_SETTING_FIELDS:
        key = field["key"]
        if key not in values:
            continue
        raw = values[key]
        if field["type"] == "int":
            try:
                int(raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"'{key}' mora biti celo število")
        if field["type"] == "json":
            parsed = raw if isinstance(raw, dict) else None
            if parsed is None:
                try:
                    parsed = _json.loads(raw or "{}")
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail=f"'{key}' mora biti veljaven JSON")
            values[key] = _json.dumps(parsed, ensure_ascii=False)
        elif isinstance(raw, (dict, list)):
            values[key] = _json.dumps(raw, ensure_ascii=False)

    for key, value in values.items():
        set_school_setting(db, school.id, key, value)
    db.commit()

    user = get_request_user(request, db)
    log_audit(db, user.id if user else None, user.username if user else "?",
              _SETTINGS_AUDIT_ACTION,
              f"school_id={school.id}, keys={','.join(sorted(values.keys()))}")
    return _settings_payload(db, school)


# ═══════════════════════════════════════════════════════════════════════
# HTML strani
# ═══════════════════════════════════════════════════════════════════════

@router.get("/schools", response_class=HTMLResponse)
def schools_page(request: Request, db: Session = Depends(get_db)):
    """Pregled šol in obrazec za novo šolo (samo glavni admin)."""
    user = get_request_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login")
    if not is_main_admin(user):
        return HTMLResponse("Dostop samo za glavnega admina.", status_code=403)

    rows = db.query(School).order_by(School.id).all()
    schools_data = [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "is_active": s.is_active,
            "aliases": [a.alias for a in s.aliases],
            "counts": _school_counts(db, s.id),
        }
        for s in rows
    ]
    return templates.TemplateResponse("schools.html", {
        "request": request,
        "schools": schools_data,
        "default_slug": slugify(schools_data[0]["name"]) if schools_data else "",
    })


@router.get("/schools/open/{school_id}")
def open_school(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Glavni admin »vstopi« v šolo — nastavi piškotek school_ctx in odpri urnik.

    Zakaj piškotek? Ker glavni admin ni vezan na šolo; s tem izbere,
    katero šolo gleda/ureja prek kanoničnih poti.
    """
    _require_main_admin(request, db)
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Šola ne obstaja")
    response = RedirectResponse(url="/rezervacije", status_code=303)
    response.set_cookie(key="school_ctx", value=str(school.id), httponly=True, samesite="lax")
    return response


@router.get("/settings", response_class=HTMLResponse)
def school_settings_page(
    request: Request,
    school_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Stran za urejanje nastavitev šole (šolski admin ali glavni admin)."""
    user = get_request_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login")
    try:
        school = _manageable_school(db, request, school_id)
    except HTTPException as exc:
        return HTMLResponse(exc.detail, status_code=exc.status_code)

    return templates.TemplateResponse("school_settings.html", {
        "request": request,
        "school": {"id": school.id, "slug": school.slug, "name": school.name,
                   "aliases": [a.alias for a in school.aliases]},
        "fields": SCHOOL_SETTING_FIELDS,
        "values": get_school_config(db, school.id).effective_values(),
        "is_main_admin": is_main_admin(user),
    })
