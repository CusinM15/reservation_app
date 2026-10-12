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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.templating import make_templates
from app.i18n import t
from sqlalchemy.orm import Session

from app.database import get_db
from app.app_settings import selling_config, selling_enabled
from app.subscriptions import subscription_state
from app.models import School, SchoolAlias, User, Reservation, Assessment, ActivityDay, RoleEnum
from app.audit import log_audit
from app.security import get_current_user_id, sign_user_id
from app.security import inactivity_timeout_ms
from app.tenancy import (
    ASSESSMENT_RULE_DEFAULTS,
    MAIN_ADMIN_ROLE,
    SCHOOL_ADMIN_ROLE,
    SCHOOL_SETTING_FIELDS,
    SCHOOL_SETTING_KEYS,
    add_school_alias,
    apply_admin_email,
    create_school,
    delete_school_data,
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
    sync_admin_user_email,
    TEST_EMAIL_PLACEHOLDER,
)
from app.backup_restore import DOMAINS, DOMAIN_LABELS, restore_domain
from app.school_backup import backup_filename, build_school_sql, send_backup_email
from app.config import settings

router = APIRouter(tags=["schools"])
templates = make_templates()

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
# API — varnostna kopija (.sql) ene šole po e-pošti
# ═══════════════════════════════════════════════════════════════════════

@router.post("/api/schools/{school_id}/backup")
def make_school_backup(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Sestavi .sql varnostno kopijo TE šole in jo pošlje po e-pošti.

    Kopija vsebuje IZKLJUČNO podatke te šole (vsaka poizvedba je omejena na
    school_id). Naslov: BACKUP_EMAIL šole, sicer ADMIN_EMAIL.
    Vrne, ali je bilo pošiljanje uspešno, in povzetek po tabelah.
    """
    school = _manageable_school(db, request, school_id)
    config = get_school_config(db, school.id)
    sql, summary = build_school_sql(db, school)
    recipient = config.BACKUP_EMAIL or config.ADMIN_EMAIL
    filename = backup_filename(school)
    size = len(sql.encode("utf-8"))

    sent, message = send_backup_email(config, recipient, school, sql, filename)

    user = get_request_user(request, db)
    log_audit(
        db, user.id if user else None, user.username if user else "?",
        "school_backup",
        f"school_id={school.id}, email={recipient or '-'}, file={filename}, "
        f"bytes={size}, sent={sent}, tables={summary}",
        school_id=school.id,
    )
    return {
        "sent": sent,
        "message": message,
        "email": recipient,
        "filename": filename,
        "bytes": size,
        "tables": summary,
    }


# ═══════════════════════════════════════════════════════════════════════
# API — brisanje šole (samo glavni admin)
# ═══════════════════════════════════════════════════════════════════════

@router.delete("/api/schools/{school_id}")
def delete_school(school_id: int, request: Request, db: Session = Depends(get_db)):
    """Izbriše šolo in VSE njene podatke (samo glavni admin).

    Privzete šole ni mogoče izbrisati — ob zagonu bi jo bootstrap znova
    ustvaril, zato bi uporabnik mislil, da brisanje ne deluje.
    """
    admin = _require_main_admin(request, db)
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Šola ne obstaja")
    if school.slug == settings.DEFAULT_SCHOOL_SLUG:
        raise HTTPException(
            status_code=400,
            detail=(f"Privzete šole »{school.name}« ni mogoče izbrisati — "
                    f"ob zagonu aplikacije se znova ustvari."),
        )

    name, slug = school.name, school.slug
    counts = delete_school_data(db, school)
    db.commit()
    # Zapis v dnevnik: school_id=None, ker šole ni več (ni tuje-ključne vezi).
    log_audit(
        db, admin.id, admin.username, "delete_school",
        f"school_id={school_id}, slug={slug}, name={name}, deleted={counts}",
        school_id=None,
    )
    return {"message": f"Šola »{name}« je izbrisana.", "deleted": counts}


# ═══════════════════════════════════════════════════════════════════════
# API — obnova iz varnostne kopije (.sql)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/api/schools/{school_id}/restore")
async def restore_from_backup(
    school_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
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

    # Kdo obnavlja: id in uporabniško ime shranimo PREJ. Obnova področja
    # »uporabniki« izbriše in znova vstavi vrstice te šole, zato objekt User po
    # obnovi ni več veljaven — vsak dostop do njega vrže ObjectDeletedError in
    # stran je javila 500, čeprav je obnova uspela.
    actor = get_request_user(request, db)
    actor_id = actor.id if actor else None
    actor_username = actor.username if actor else None
    actor_is_main = bool(actor and is_main_admin(actor))

    try:
        summary = restore_domain(
            db, school.id, content, domain,
            fallback_user_id=actor_id,
        )
        # Če smo obnovili nastavitve, uskladimo še e-pošto glavnega admin računa
        # (nastavitev ADMIN_EMAIL → users.email). Če naslov uporablja drug račun,
        # obnova vseeno uspe — le opozorilo zapišemo v povzetek.
        if "school_settings" in summary["tables"]:
            admin_email = get_school_config(db, school.id).ADMIN_EMAIL
            _changes, conflict = sync_admin_user_email(db, school.id, admin_email)
            if conflict:
                summary["warnings"].append(
                    f"E-pošta admina ni usklajena: {conflict}"
                )
            else:
                apply_admin_email(db, school.id, admin_email)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Obnova ni uspela: {exc}")

    # Sveži sklic na račun, ki je obnavljal: isti uporabnik ima po obnovi lahko
    # NOV id (vrstice so bile znova vstavljene). Brez tega bi dnevnik padel na
    # tujem ključu, seja pa bi kazala na neobstoječ (ali celo tuj) račun.
    log_user_id = actor_id
    if actor_username:
        query = db.query(User).filter(User.username == actor_username)
        if not actor_is_main:
            query = query.filter(User.school_id == school.id)
        fresh = query.first()
        if fresh is None:
            log_user_id = None
        else:
            log_user_id = fresh.id
            if actor_id is not None and fresh.id != actor_id:
                # Seja je vezana na id → osvežimo piškotek, da uporabnik ostane prijavljen.
                response.set_cookie(
                    key="user_id", value=sign_user_id(fresh.id),
                    httponly=True, samesite="lax",
                )
                summary["warnings"].append(
                    "Vaš račun je bil obnovljen z novim id-jem — seja je bila "
                    "osvežena, zato ostanete prijavljeni."
                )

    log_audit(
        db, log_user_id, actor_username or "?",
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

    # Polja tipa »password« (npr. SMTP geslo) se v obrazcu NIKOLI ne predizpolnijo,
    # zato prazna vrednost pomeni »pusti obstoječe geslo« in je ne zapišemo čez.
    for field in SCHOOL_SETTING_FIELDS:
        if field["type"] == "password" and not str(values.get(field["key"], "")).strip():
            values.pop(field["key"], None)

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
        if field["type"] == "lang" and str(values[key]).strip().lower() not in ("sl", "en"):
            raise HTTPException(status_code=400, detail=f"'{key}' mora biti 'sl' ali 'en'")

    # Seznam ali slovar se shrani kot JSON — za VSAKO nastavitev, tudi tisto,
    # ki ni v obrazcu (npr. PROSTORI_QTY je seznam prostorov »kot Tablice«).
    # Brez tega bi Python seznam shranili kot "['tablice']", kar ni berljivo.
    for key, raw_value in list(values.items()):
        if isinstance(raw_value, (dict, list)):
            values[key] = _json.dumps(raw_value, ensure_ascii=False)

    # E-pošta šolskega admina je VEZANA na nastavitev ADMIN_EMAIL: admin račun
    # te šole dobi natanko ta naslov (glej sync_admin_user_email). Če naslov že
    # uporablja drug račun iste šole (UNIQUE school_id+email), nastavitev NI
    # shranjena in uporabnik dobi JASNO razlago, kaj naj uredi.
    admin_email_changes: list[str] = []
    if "ADMIN_EMAIL" in values:
        admin_email_changes, conflict = sync_admin_user_email(
            db, school.id, values.get("ADMIN_EMAIL")
        )
        if conflict:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=(f"Nastavitve niso shranjene: {conflict}. "
                        f"Uredite ali izbrišite tisti račun, nato poskusite znova."),
            )
        # Naslov zapišemo v GLAVNI admin račun te šole.
        apply_admin_email(db, school.id, values.get("ADMIN_EMAIL"))

    for key, value in values.items():
        set_school_setting(db, school.id, key, value)
    db.commit()

    user = get_request_user(request, db)
    details = f"school_id={school.id}, keys={','.join(sorted(values.keys()))}"
    if admin_email_changes:
        details += f", admin_email={'; '.join(admin_email_changes)}"
    log_audit(db, user.id if user else None, user.username if user else "?",
              _SETTINGS_AUDIT_ACTION, details)
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
            "inactivity_timeout_ms": inactivity_timeout_ms(user),
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


def _school_chooser_html(db: Session) -> str:
    """Preprosta stran za glavnega admina: izbira šole za /settings.

    Zakaj? Glavni admin ni vezan na šolo; če ni izbral šole (spustni seznam
    »Šola« oz. pot šole), nastavitev ni mogoče prikazati. Prej je dobil golo
    napako 400, zdaj pa dobi seznam šol s povezavami na njihove nastavitve.
    """
    from html import escape

    rows = db.query(School).order_by(School.name).all()
    items = "".join(
        f'<li><a href="/settings?school_id={s.id}">{escape(str(s.name))}</a> '
        f'<span style="color:#888;font-size:0.85rem;">(/{escape(str(s.slug))})</span></li>'
        for s in rows
    )
    return (
        "<!DOCTYPE html><html lang=\"sl\"><head><meta charset=\"UTF-8\">"
        "<title>Nastavitve šole</title></head><body "
        "style=\"font-family:Arial,sans-serif;margin:40px;max-width:640px;\">"
        "<h2>⚙️ Nastavitve šole</h2>"
        "<p>Izberite šolo, katere nastavitve želite urediti:</p>"
        f"<ul style=\"line-height:1.9;\">{items}</ul>"
        "<p><a href=\"/schools\">← Pregled vseh šol</a> &nbsp;|&nbsp; "
        "<a href=\"/rezervacije\">← Aplikacija</a></p>"
        "</body></html>"
    )


def _demo_setup_items() -> list[dict]:
    """Primer postavk z PSEVDO podatki — za javni predogled navodil
    (neprijavljen uporabnik). Vrednosti so izmišljene in služijo le prikazu,
    kako je videti izpolnjena šola; ena postavka je namenoma ✗, da je vidna
    tudi oblika »še uredi«.
    """
    return [
        {
            "naslov": t('onb_admin_email', 'E-pošta šolskega admina'),
            "opis": t('onb_admin_email_d', 'Naslov, na katerega prejmete obvestila in povezavo za obnovitev gesla.'),
            "ok": True,
            "trenutno": "ravnatelj@guest.arnes.si",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_smtp_user', 'SMTP uporabniško ime'),
            "opis": t('onb_smtp_user_d', 'Uporabniško ime za prijavo v poštni strežnik (npr. Arnes).'),
            "ok": True,
            "trenutno": "ravnatelj",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_smtp_pass', 'SMTP geslo'),
            "opis": t('onb_smtp_pass_d', 'Geslo za pošiljanje pošte.'),
            "ok": True,
            "trenutno": "Geslo123",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_from', 'Naslov pošiljatelja (From)'),
            "opis": t('onb_from_d', "Naslov, s katerim aplikacija pošilja pošto (obvestila, obnovitev gesla, varnostne kopije). Nova šola dobi testni naslov — zamenjajte ga s svojim, sicer pošta ne bo dostavljena."),
            "ok": False,
            "trenutno": "test@example.invalid",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_backup', 'E-pošta za varnostne kopije'),
            "opis": t('onb_backup_d', 'Kam naj gre nočna varnostna kopija podatkov šole.'),
            "ok": True,
            "trenutno": "arhiv@guest.arnes.si",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_server', 'SMTP strežnik (pošiljanje pošte)'),
            "opis": t('onb_server_d', 'Strežnik za pošiljanje pošte. Privzeto so vpisani podatki ponudnika — za svojo šolo vpišite svojega (npr. Arnes).'),
            "ok": True,
            "trenutno": "mail.arnes.si",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_razredi', 'Razredi'),
            "opis": t('onb_razredi_d', 'Seznam oddelkov, vejica-ločeno (npr. 1. a, 2. a, 9. č).'),
            "ok": True,
            "trenutno": "1. a, 1. b, 2. a, 2. b, 3. a",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_prostori', 'Prostori in oprema'),
            "opis": t('onb_prostori_d', 'Prostori, ki jih je mogoče rezervirati, in njihove kapacitete.'),
            "ok": True,
            "trenutno": "telovadnica, računalnica, knjižnica, tablice",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_uporabniki', 'Uporabniki (učitelji in vodstvo)'),
            "opis": t('onb_uporabniki_d', 'Ustvarite račune za učitelje in vodstvo — vsak dobi svoje uporabniško ime in geslo.'),
            "ok": True,
            "trenutno": t('onb_users_demo', '28 aktivnih uporabnikov, od tega 25 učiteljev'),
            "kje": "/auth/admin/users",
            "kje_napis": t('onb_kje_uporabniki', 'Uporabniki'),
        },
    ]


@router.get("/nastavitev", response_class=HTMLResponse)
def setup_guide_page(
    request: Request,
    school_id: int | None = Query(None),
    demo: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Navodila za nastavitev šole — kaj mora admin urediti, da app dela pravilno.

    Kazalniki ✓/✗ se izračunajo iz DEJANSKIH nastavitev šole, zato admin takoj
    vidi, kaj še manjka (npr. testni naslov pošiljatelja, ki ga dobi nova šola ob
    registraciji, mora zamenjati s svojim).

    S parametrom ``?demo=1`` (ali za neprijavljenega uporabnika prek povezave na
    prijavni strani) se prikaže PREDOGLED s psevdo podatki — brez prijave, da
    obiskovalec vidi, kako so videti navodila, preden si ustvari račun.
    """
    user = get_request_user(request, db)
    if not user:
        if demo:
            items = _demo_setup_items()
            return templates.TemplateResponse(
                            "nastavitev.html",
                            {
                                "request": request,
                                "inactivity_timeout_ms": 0,
                                "demo": True,
                    "school": {"name": "OŠ Primer", "slug": "primer"},
                    "items": items,
                    "stevilo_ok": sum(1 for i in items if i["ok"]),
                    "stevilo_vseh": len(items),
                    "is_main_admin": False,
                    "prodaja": selling_config(db),
                },
            )
        return RedirectResponse(url="/auth/login")
    try:
        school = _manageable_school(db, request, school_id)
    except HTTPException as exc:
        if exc.status_code == 400 and is_main_admin(user):
            return HTMLResponse(_school_chooser_html(db), status_code=200)
        return HTMLResponse(exc.detail, status_code=exc.status_code)

    cfg = get_school_config(db, school.id)
    testni = TEST_EMAIL_PLACEHOLDER

    def _nastavljeno(value: str | None) -> bool:
        text = (value or "").strip()
        return bool(text) and text != testni

    uporabniki = (
        db.query(User).filter(User.school_id == school.id, User.is_active == True).count()  # noqa: E712
    )
    ucitelji = (
        db.query(User)
        .filter(User.school_id == school.id, User.role == RoleEnum.teacher, User.is_active == True)  # noqa: E712
        .count()
    )
    stanje = subscription_state(db, school.id)

    items = [
        {
            "naslov": t('onb_admin_email', 'E-pošta šolskega admina'),
            "opis": t('onb_admin_email_d', 'Naslov, na katerega prejmete obvestila in povezavo za obnovitev gesla.'),
            "ok": _nastavljeno(cfg.ADMIN_EMAIL),
            "trenutno": cfg.ADMIN_EMAIL,
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_smtp_user', 'SMTP uporabniško ime'),
            "opis": t('onb_smtp_user_d', 'Uporabniško ime za prijavo v poštni strežnik (npr. Arnes).'),
            "ok": bool((cfg.get_str("MAIL_USERNAME", "") or "").strip()),
            "trenutno": cfg.get_str("MAIL_USERNAME", "") or "",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_smtp_pass', 'SMTP geslo'),
            "opis": t('onb_smtp_pass_d', 'Geslo za pošiljanje pošte.'),
            "ok": bool((cfg.get_str("MAIL_PASSWORD", "") or "").strip()),
            "trenutno": cfg.get_str("MAIL_PASSWORD", "") or "",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_from', 'Naslov pošiljatelja (From)'),
            "opis": t('onb_from_d', "Naslov, s katerim aplikacija pošilja pošto (obvestila, obnovitev gesla, varnostne kopije). Nova šola dobi testni naslov — zamenjajte ga s svojim, sicer pošta ne bo dostavljena."),
            "ok": _nastavljeno(cfg.MAIL_FROM),
            "trenutno": cfg.MAIL_FROM,
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_backup', 'E-pošta za varnostne kopije'),
            "opis": t('onb_backup_d', 'Kam naj gre nočna varnostna kopija podatkov šole.'),
            "ok": _nastavljeno(cfg.BACKUP_EMAIL),
            "trenutno": cfg.BACKUP_EMAIL,
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_server', 'SMTP strežnik (pošiljanje pošte)'),
            "opis": t('onb_server_d', 'Strežnik za pošiljanje pošte. Privzeto so vpisani podatki ponudnika — za svojo šolo vpišite svojega (npr. Arnes).'),
            "ok": bool((cfg.MAIL_SERVER or "").strip()) and bool((cfg.MAIL_USERNAME or "").strip())
                  and bool(cfg.get_str("MAIL_PASSWORD", "")),
            "trenutno": cfg.MAIL_SERVER or "",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_razredi', 'Razredi'),
            "opis": t('onb_razredi_d', 'Seznam oddelkov, vejica-ločeno (npr. 1. a, 2. a, 9. č).'),
            "ok": bool(cfg.RAZREDI),
            "trenutno": ", ".join(cfg.RAZREDI) if cfg.RAZREDI else "",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_prostori', 'Prostori in oprema'),
            "opis": t('onb_prostori_d', 'Prostori, ki jih je mogoče rezervirati, in njihove kapacitete.'),
            "ok": bool(cfg.PROSTORI),
            "trenutno": ", ".join(cfg.PROSTORI) if cfg.PROSTORI else "",
            "kje": "/settings",
            "kje_napis": t('onb_kje_nastavitve', 'Nastavitve šole'),
        },
        {
            "naslov": t('onb_uporabniki', 'Uporabniki (učitelji in vodstvo)'),
            "opis": t('onb_uporabniki_d', 'Ustvarite račune za učitelje in vodstvo — vsak dobi svoje uporabniško ime in geslo.'),
            "ok": ucitelji > 0,
            "trenutno": f"{uporabniki} {t('onb_aktivnih', 'aktivnih uporabnikov, od tega')} {ucitelji} {t('onb_uciteljev', 'učiteljev')}",
            "kje": "/auth/admin/users",
            "kje_napis": t('onb_kje_uporabniki', 'Uporabniki'),
        },
    ]

    # Postavka »Naročnina« ima smisel le tam, kjer se naročnine prodajajo.
    # Na šolski namestitvi (prodaja izklopljena) je ne prikazujemo — navodila za
    # nastavitev naj bodo o nastavitvah šole, ne o plačevanju.
    if selling_enabled(db):
        items.append({
            "naslov": t('onb_narocnina', 'Naročnina'),
            "opis": t('onb_narocnina_d2', 'Uporaba je veljavna, ko je naročnina potrjena (tudi pri ceni 0 € jo je treba redno obnoviti).'),
            "ok": bool(stanje.get("active")),
            "trenutno": (
                f"{t('onb_veljavna_do', 'veljavna do')} {stanje['until'].strftime('%d. %m. %Y')}"
                if stanje.get("until") and stanje.get("active")
                else t('set_ni_veljavna', 'ni veljavna')
            ),
            "kje": "/narocnina",
            "kje_napis": t('onb_narocnina', 'Naročnina'),
        })

    return templates.TemplateResponse(
            "nastavitev.html",
            {
                "request": request,
                "inactivity_timeout_ms": inactivity_timeout_ms(user),
                "school": school,
            "items": items,
            "stevilo_ok": sum(1 for i in items if i["ok"]),
            "stevilo_vseh": len(items),
            "is_main_admin": is_main_admin(user),
            "prodaja": selling_config(db),
        },
    )


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
        # Glavni admin, ki ni izbral šole (in jih ima več), prej ni dobil niti
        # strani niti povezave — samo golo napako 400. Zdaj mu ponudimo izbiro
        # šole direktno na strani, da dostop do /settings ne »pade«.
        if exc.status_code == 400 and is_main_admin(user):
            return HTMLResponse(_school_chooser_html(db), status_code=200)
        return HTMLResponse(exc.detail, status_code=exc.status_code)

    cfg = get_school_config(db, school.id)
    values = cfg.effective_values()

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

    # RAZREDI: vsak razred v SVOJI vrstici (iz vejica-ločenega seznama).
    razredi_rows = [r for r in cfg.RAZREDI if r]

    # ŠTEVILA: imenovane številske spremenljivke v vrsticah (ime + vrednost).
    # Ločen objekt (kot urnik) — na imena se vežejo prostori spodaj.
    stevila_rows = [{"name": name, "value": value} for name, value in cfg.STEVILA.items()]

    # PROSTORI: vsak prostor v svoji vrstici + vezava na številsko spremenljivko
    # (kljukica »število« + spustni seznam imen iz STEVILA).
    prostori_stevilo = cfg.PROSTORI_STEVILO
    prostori_rows = [
        {"name": p, "stevilo": prostori_stevilo.get(p, "")}
        for p in cfg.PROSTORI
    ]

    return templates.TemplateResponse("school_settings.html", {
            "request": request,
            "inactivity_timeout_ms": inactivity_timeout_ms(user),
            "school": {"id": school.id, "slug": school.slug, "name": school.name,
                   "aliases": [a.alias for a in school.aliases]},
        "fields": SCHOOL_SETTING_FIELDS,
        "values": values,
        "schedule_rows": schedule_rows,
        "prostori_rows": prostori_rows,
        "razredi_rows": razredi_rows,
        "stevila_rows": stevila_rows,
        # Naslov, kamor gre »Naredi backup« (BACKUP_EMAIL šole, sicer ADMIN_EMAIL).
        "backup_email": (cfg.BACKUP_EMAIL or cfg.ADMIN_EMAIL or ""),
        "is_main_admin": is_main_admin(user),
        # Naročnina: stanje (veljavnost) + nastavitve prodaje — šolski admin tu
        # vidi, da lahko naročnino kupi oziroma podaljša na /narocnina.
        "narocnina": subscription_state(db, school.id),
        "prodaja": selling_config(db),
    })
