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
    remove_school_alias,
    request_school_id,
    role_value,
    set_school_setting,
    get_school_config,
    slugify,
)
from app.backup_restore import DOMAINS, DOMAIN_LABELS, restore_domain

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


@router.delete("/api/schools/{school_id}/aliases/{alias}")
def delete_school_alias(
    school_id: int,
    alias: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Odstrani pot šole (npr. podvojen/zgodovinski alias).

    Zakaj to potrebujemo? Ena šola lahko ima več aliasov (generirani + stari).
    Če je kakšen odveč, ga je mogoče odstraniti — brez tega bi ostajale
    zavajajoče povezave v pregledu šol.
    """
    school = _manageable_school(db, request, school_id)
    try:
        remove_school_alias(db, school.id, alias)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    user = get_request_user(request, db)
    log_audit(db, user.id if user else None, user.username if user else "?",
              "delete_school_alias", f"school_id={school.id}, alias={alias}",
              school_id=school.id)
    return {"message": f"Pot '{alias}' odstranjena.", "aliases": [a.alias for a in school.aliases]}


# ═══════════════════════════════════════════════════════════════════════
# API — obnova iz varnostne kopije (.sql)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/api/schools/{school_id}/restore")
async def restore_from_backup(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Obnovi podatke šole iz naložene .sql varnostne kopije.

    Obrazec (multipart/form-data):
      - file:   .sql datoteka (pg_dump, plain)
      - domain: dejavnosti | rezervacije | ocenjevanje | vse

    Vsebina izbranih tabel za TO šolo se izbriše in znova vstavi iz kopije.
    Vrstice drugih šol ostanejo nedotaknjene (`WHERE school_id = ...`).
    """
    school = _manageable_school(db, request, school_id)

    form = await request.form()
    domain = str(form.get("domain") or "").strip().lower()
    upload = form.get("file")
    if domain not in DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Neveljavno področje. Dovoljeno: {', '.join(DOMAINS.keys())}",
        )
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Manjka datoteka (polje 'file').")

    raw = await upload.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Naložena datoteka je prazna.")
    content = raw.decode("utf-8", errors="replace")

    try:
        summary = restore_domain(db, school.id, content, domain)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Obnova ni uspela: {exc}")

    user = get_request_user(request, db)
    log_audit(
        db, user.id if user else None, user.username if user else "?",
        "restore_from_backup",
        f"school_id={school.id}, domain={domain}, "
        f"tables={ {t: v['inserted'] for t, v in summary['tables'].items()} }",
        school_id=school.id,
    )
    return summary


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
        "current_username": user.username,
    })


@router.get("/schools/open/{school_id}")
def open_school(
    school_id: int,
    request: Request,
    next_url: str | None = Query(None, alias="next"),
    db: Session = Depends(get_db),
):
    """Glavni admin izbere šolo — nastavi piškotek school_ctx.

    Zakaj piškotek? Ker glavni admin ni vezan na šolo; s tem izbere, katero
    šolo gleda IN ureja prek kanoničnih poti (poti šol torej niso potrebne).

    school_id = 0 pomeni »vse šole« (izbira se počisti — branje čez vse šole,
    pisanje zavrnjeno, ker ni jasno, kateri šoli naj zapis pripada).
    next: kam naj se vrne (npr. trenutna stran, da uporabnik ne skoči na urnik).
    """
    _require_main_admin(request, db)
    target = next_url if (next_url or "").startswith("/") else "/rezervacije"

    if school_id == 0:
        response = RedirectResponse(url=target, status_code=303)
        response.delete_cookie("school_ctx")
        return response

    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Šola ne obstaja")
    response = RedirectResponse(url=target, status_code=303)
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

    values = get_school_config(db, school.id).effective_values()

    # URNIK: v obrazcu je vsaka ura v SVOJI VRSTICI (ne surov JSON), ker je
    # tako urejanje za šolskega admina preprosto in pregledno. Tu pripravimo
    # vrstice iz shranjene vrednosti; JavaScript jih ob shranjevanju sestavi
    # nazaj v JSON, zato strežnik in koledar prejmeta enako obliko kot prej.
    import json as _json
    schedule_rows = []
    try:
        parsed = _json.loads(values.get("SCHEDULE") or "{}")
    except (TypeError, ValueError):
        parsed = {}
    if isinstance(parsed, dict):
        def _sort_key(item):
            try:
                return (0, int(item))
            except (TypeError, ValueError):
                return (1, str(item))
        for key in sorted(parsed.keys(), key=_sort_key):
            schedule_rows.append({"index": str(key), "value": str(parsed[key])})

    return templates.TemplateResponse("school_settings.html", {
        "request": request,
        "school": {"id": school.id, "slug": school.slug, "name": school.name,
                   "aliases": [a.alias for a in school.aliases]},
        "fields": SCHOOL_SETTING_FIELDS,
        "values": values,
        "schedule_rows": schedule_rows,
        "is_main_admin": is_main_admin(user),
    })
