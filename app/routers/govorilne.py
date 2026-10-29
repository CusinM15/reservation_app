# ─────────────────────────────────────────────────────────────────────────
# app/routers/govorilne.py — Prijave staršev na govorilne ure
#
# Namen: Javna stran /govorilne, kjer starš izbere učitelja in 15-minutni
# termin govorilnih ur. Podatki o učiteljih/terminih so shranjeni PO ŠOLI
# v school_settings (ključ GOVORILNE_KONFIG), s privzetkom iz
# app/govorilne_podatki.py (vir: https://ostcjesenice.splet.arnes.si/za-starse/govorilne-ure/).
#
# UREJANJE (na /govorilne/ure, 24. 10. 2026):
#   - Admin/vodstvo/glavni admin uredi POPOLDANSKE govorilne ure (kdaj so)
#     in termine vseh učiteljev.
#   - Vsak učitelj uredi SVOJE dopoldanske govorilne (dan/uro), predmet in
#     razred iz spustnega seznama (če je razrednik).
#
# Pravila:
#   - /govorilne in /govorilne/api/* so JAVNI (starši se ne prijavljajo).
#   - /govorilne/prijave je za prijavljene: učitelj vidi samo svoje prijave;
#     vodstvo, šolski admin in glavni admin vidijo vse prijave šole.
#   - En termin = 15 minut. Popoldanski termini so uradni četrtki iz spletne
#     strani šole; dopoldanski so dogovorjeni (vsak učitelj svoj dan/uro).
#   - Prijave se samodejno izbrišejo 24 ur po koncu termina govorilnih ur.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
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
    URNIKI,
    ZBONJEC_URL,
    _urnik_ucitelja_za,
)

router = APIRouter(tags=["govorilne"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Koliko minut traja en termin (privzeto 15; šola lahko nastavi v /govorilne/ure).
TERMIN_MINUT = 15
# Začetek popoldanskih govorilnih ur (uradni četrtek).
POPOLDAN_ZACETEK = "17:30"
# Osnovno trajanje popoldanskih govorilnih ur (1 ura — toliko terminov
# ponudimo najprej; ko so vsi zasedeni, dodajamo po en → POPOLDAN_MAX_UR).
POPOLDAN_OSNOVNI_MIN = 60
# Največ koliko UR lahko trajajo popoldanske govorilne OD ZAČETKA (17:30 →
# do 22:30). Ko je osnovna ura polna, se doda po en nov termin do te meje.
POPOLDAN_MAX_UR = 5
# Prijave se samodejno izbrišejo 24 ur po koncu termina govorilnih ur.
HRAMBA_UR = 24
# Termin je staršem viden največ 24 ur po začetku (starejši izginejo).
TERMIN_MAX_STAROST_UR = 24

# Ključ v school_settings, kjer je shranjena per-šola govorilna konfiguracija.
GOVORILNE_SETTING_KEY = "GOVORILNE_KONFIG"


# ═══════════════════════════════════════════════════════════════════════
# Konfiguracija govorilnih ur — branje/pisanje v bazi (po šoli)
# ═══════════════════════════════════════════════════════════════════════

def _default_cfg() -> dict:
    """Privzeta konfiguracija (seed) — iz hardkodiranega modula."""
    return {
        "ucitelji": UCITELJI,
        "popoldan_datumi": POPOLDAN_DATUMI,
        "ura_zacetki": URA_ZACETKI,
        "urniki": URNIKI,
        "zvonec_url": ZBONJEC_URL,
        "dopoldan_teden": GOVORILNE_DOPOLDAN_TEDEN,
        "termin_minut": TERMIN_MINUT,
        "popoldan_zacetek": POPOLDAN_ZACETEK,
        "popoldan_osnovni_min": POPOLDAN_OSNOVNI_MIN,
        "popoldan_max_ur": POPOLDAN_MAX_UR,
    }


def _cfgs_iz_sklada(raw: str | None) -> dict | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _int_keys(d: dict) -> dict:
    """Pretvori string ključe slovarja v int, kjer je mogoče (ura_zacetki)."""
    out = {}
    for k, v in d.items():
        try:
            out[int(k)] = v
        except (TypeError, ValueError):
            out[k] = v
    return out


def _load_cfg(db: Session, school_id: int | None) -> dict:
    """Preberi govorilno konfiguracijo šole; če je ni, jo seed-aj iz modula
    in shrani (da je v produkciji od prvega dostopa napolnjena)."""
    cfg = _default_cfg()
    if school_id is None:
        return cfg
    from app.models import SchoolSetting
    row = db.query(SchoolSetting).filter(
        SchoolSetting.school_id == school_id,
        SchoolSetting.key == GOVORILNE_SETTING_KEY,
    ).first()
    saved = _cfgs_iz_sklada(row.value if row else None)
    if saved is not None:
        # Merge — ohrani vse ključe tudi, če kdo ročno izpusti.
        base = _default_cfg()
        base.update(saved)
        # ura_zacetki v JSON ima string ključe (JSON ne pozna int ključev);
        # nazaj v int, da u["ura"] (int) najde začetek ure.
        base["ura_zacetki"] = _int_keys(base.get("ura_zacetki") or {})
        return base
    # Seed iz privzetkov in shrani (spravi v produkcijo za to šolo).
    # ⚠️ VARNO PRED CROSS-ŠOLO PRELIVOM: ucitelji iz modula (govorilne_podatki.py)
    # pripadajo SAMO privzeti (OSTC) šoli. Vsaka DRUGA šola, ki še nima svoje
    # konfiguracije, se seed-a z PRAZNIM seznamom učiteljev — nikoli ne sme
    # podedovati učiteljev druge šole (iz ene šole se ne sme videti druge).
    if school_id != _default_school_id(db):
        cfg["ucitelji"] = []
    text = json.dumps(cfg, ensure_ascii=False)
    if row is None:
        db.add(SchoolSetting(school_id=school_id, key=GOVORILNE_SETTING_KEY, value=text))
    else:
        row.value = text
    try:
        db.commit()
    except Exception:
        db.rollback()
    return cfg


def _save_cfg(db: Session, school_id: int | None, cfg: dict) -> None:
    """Shrani govorilno konfiguracijo šole nazaj v bazo."""
    if school_id is None:
        raise HTTPException(status_code=400, detail="Ni določena šola konfiguracije")
    from app.models import SchoolSetting
    text = json.dumps(cfg, ensure_ascii=False)
    row = db.query(SchoolSetting).filter(
        SchoolSetting.school_id == school_id,
        SchoolSetting.key == GOVORILNE_SETTING_KEY,
    ).first()
    if row is None:
        db.add(SchoolSetting(school_id=school_id, key=GOVORILNE_SETTING_KEY, value=text))
    else:
        row.value = text
    db.commit()


# ═══════════════════════════════════════════════════════════════════════
# Pomožne funkcije — termini učitelja
# ═══════════════════════════════════════════════════════════════════════

def _ucitelj_by_ime(ime: str, ucitelji: list | None = None) -> dict | None:
    """Poišči učitelja po polnem imenu (case-insensitive, strpi se s presledki).

    ``ucitelji`` — per-šola seznam; če None, uporabi privzete (modul).
    """
    needle = re.sub(r"\s+", " ", ime or "").strip().lower()
    seznam = ucitelji if ucitelji is not None else UCITELJI
    for u in seznam:
        if re.sub(r"\s+", " ", u["ime"]).lower() == needle:
            return u
    return None


def _opis_ucitelja(u: dict) -> str:
    """Opis ob imenu (za »Priimek Ime — predmet«, po potrebi dodan razrednik):
    razrednik → 'predmet — razrednik <razred>' (npr. 'Slovenščina — razrednik 8. a'),
    predmetni učitelj → zgolj predmet (npr. 'Angleščina'). Podatki že ločijo
    razred (razrednik) od predmeta — tu samo sestavimo izpis."""
    predmet = (u.get("predmet") or "").strip()
    razred = (u.get("razred") or "").strip()
    if razred:
        return f"{predmet} — razrednik {razred}"
    return predmet


def _ime_priimek(ime: str) -> str:
    """»Priimek Ime« — zadnja beseda (priimek) naprej: 'Barbara Potočan Iskra'
    → 'Iskra Barbara Potočan'. Konsistentno s sortom po priimkih (_priimek)."""
    deli = (ime or "").split()
    if len(deli) <= 1:
        return ime or ""
    return " ".join([deli[-1]] + deli[:-1])


_SORT_MAP = str.maketrans({"č": "cz", "ć": "cz", "š": "sz", "ž": "zs", "đ": "dz"})


def _priimek(ime: str) -> str:
    """Zadnja beseda polnega imena, transliterirana za SLOVENSKI abecedni red
    (č→cz, š→sz, ž→zs, đ→dz — da č/š/ž/đ pridejo za c/s/z/d, kot v abecedi;
    Python bi jih sicer sortiral po Unicode codepointih za vse navadne črke)."""
    return ime.rsplit(maxsplit=1)[-1].lower().translate(_SORT_MAP)


def _add_minutes(hhmm: str, minutes: int) -> str:
    """"09:30" + 15 → "09:45" (24-urni zapis, samo navzgor)."""
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    t = (h * 60 + m + minutes) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


def _term_min(cfg: dict | None = None) -> int:
    """Dolžina termina v minutah (šola nastavi; privzeto TERMIN_MINUT)."""
    cfg = cfg or _default_cfg()
    try:
        v = int(cfg.get("termin_minut") or TERMIN_MINUT)
        return v if v >= 5 else TERMIN_MINUT
    except (TypeError, ValueError):
        return TERMIN_MINUT


def _zacetki_za_ucitelja(u: dict, cfg: dict | None = None) -> dict:
    """Tabela 'šolska ura → začetek' po URNIKOVEM izbranem urniku učitelja.

    Upošteva učiteljevo polje `urnik` (npr. '1-2', '3-5', '6-9'); če ga učitelj
    nima, razbere iz njegovega razreda (razrednik). Fallback na stare globalne
    URA_ZACETKI (časovno nekoliko drugačni, a za nedoločeno varno).
    """
    cfg = cfg or _default_cfg()
    uid = _urnik_ucitelja_za(u)
    urnik = (cfg.get("urniki") or URNIKI).get(uid)
    if urnik and urnik.get("zacetki"):
        # DB-shranjene urnike JSON pretvori ključe v str → nazaj v int.
        return _int_keys(urnik["zacetki"])
    return URA_ZACETKI


def _max_solska_ura(u: dict, cfg: dict | None = None) -> int:
    """Najvišja šolska ura, ki jo učitelj sme izbrati (po njegovem urniku)."""
    return max(_zacetki_za_ucitelja(u, cfg).keys())


def _dopoldan_monday(cfg: dict | None = None) -> date | None:
    """Ponedeljek tedna naslednjih popoldanskih govorilnih ur.

    Pravilo uporabnika: dopoldanske govorilne potekajo SAMO tisti teden,
    ko so tudi popoldanske. Dopoldan termina učitelja = PON + dan
    (0=pon..4=pet) tega tedna. Če ni prihajajočih popoldanskih, dopoldanih ni.
    """
    cfg = cfg or _default_cfg()
    danes = date.today()
    for d in (cfg.get("popoldan_datumi") or POPOLDAN_DATUMI):
        dd = date.fromisoformat(d)
        if dd >= danes:
            return dd - timedelta(days=dd.weekday())
    return None


def _testni_datum(dan: int, cfg: dict | None = None) -> date | None:
    """Dopoldanski termin učitelja v tednu popoldanskih govorilnih ur.

    Vrne PONEDELJEK tega tedna + dan učitelja (0=pon..4=pet); None, če
    tisti teden ni popoldanskih govorilnih (torej tudi dopoldanskih ni).
    """
    cfg = cfg or _default_cfg()
    pon = _dopoldan_monday(cfg)
    return None if pon is None else (pon + timedelta(days=dan))


def _dopoldan_termini(u: dict, cfg: dict | None = None) -> list[dict]:
    """Dopoldanski termini učitelja — 3 × 15 min znotraj njegove šolske ure.

    Če učitelj nima fiksnega termina (po_dogovoru → None dan/ura), nima
    dopoldanskih terminov — sprejema samo popoldan (uradni četrtki).
    """
    cfg = cfg or _default_cfg()
    if u.get("po_dogovoru") or u.get("dan") is None or u.get("ura") is None:
        return []
    start = _zacetki_za_ucitelja(u, cfg).get(u["ura"])
    if not start:
        return []
    datum = _testni_datum(u["dan"], cfg)
    if datum is None:
        return []  # tisti teden ni popoldanskih govorilnih → tudi dopoldanih ni
    term_min = _term_min(cfg)
    out = []
    for i in range(45 // term_min):  # 45-min šolska ura → več terminov dolžine term_min
        od = _add_minutes(start, i * term_min)
        do = _add_minutes(od, term_min)
        out.append({"datum": datum.isoformat(), "ura_od": od, "ura_do": do})
    return out


def _popoldan_zacetek(cfg: dict | None = None) -> str:
    """Začetek popoldanskih govorilnih ur (šola nastavi; privzeto '17:30')."""
    cfg = cfg or _default_cfg()
    v = (cfg.get("popoldan_zacetek") or POPOLDAN_ZACETEK or "").strip()
    if not v:
        return POPOLDAN_ZACETEK
    try:
        h, m = map(int, v.split(":")[:2])
        if not (0 <= h < 24 and 0 <= m < 60):
            return POPOLDAN_ZACETEK
        return f"{h:02d}:{m:02d}"
    except (TypeError, ValueError):
        return POPOLDAN_ZACETEK


def _popoldan_osnovni_min(cfg: dict | None = None) -> int:
    """Osnovno trajanje popoldanskih govorilnih ur v minutah (privzeto 60)."""
    cfg = cfg or _default_cfg()
    try:
        v = int(cfg.get("popoldan_osnovni_min") or POPOLDAN_OSNOVNI_MIN)
        return v if 15 <= v <= 180 else POPOLDAN_OSNOVNI_MIN
    except (TypeError, ValueError):
        return POPOLDAN_OSNOVNI_MIN


def _popoldan_max_ur(cfg: dict | None = None) -> int:
    """Največ koliko ur lahko trajajo popoldanske govorilne (privzeto 5)."""
    cfg = cfg or _default_cfg()
    try:
        v = int(cfg.get("popoldan_max_ur") or POPOLDAN_MAX_UR)
        return v if 1 <= v <= 8 else POPOLDAN_MAX_UR
    except (TypeError, ValueError):
        return POPOLDAN_MAX_UR


def _popoldan_term_od(i: int, term_min: int, cfg: dict | None = None) -> str:
    """Začetek i-tega popoldanskega termina od začetka (privzeto 17:30)."""
    return _add_minutes(_popoldan_zacetek(cfg), i * term_min)


def _popoldan_osnovnih_termov(cfg: dict | None = None) -> int:
    """Koliko terminov pokriva osnovno trajanje popoldanskih govorilnih ur."""
    return max(1, _popoldan_osnovni_min(cfg) // _term_min(cfg))


def _popoldan_max_termov(cfg: dict | None = None) -> int:
    """Največ možnih popoldanskih terminov: do _popoldan_max_ur ur od začetka."""
    return max(1, (_popoldan_max_ur(cfg) * 60) // _term_min(cfg))


def _popoldan_odobrenih_termov(datum: str, zauzeti: set, cfg: dict | None = None) -> int:
    """Koliko popoldanskih terminov ponuditi za dan: osnovno 1 uro, nato pa
    po en nov termin dodajamo, dokler so vsi trenutni termini zasedeni —
    največ do POPOLDAN_MAX_UR ur od začetka (17:30)."""
    cfg = cfg or _default_cfg()
    term_min = _term_min(cfg)
    n = _popoldan_osnovnih_termov(cfg)
    max_t = _popoldan_max_termov(cfg)
    while n < max_t:
        vseh = all((datum, _popoldan_term_od(i, term_min, cfg)) in zauzeti for i in range(n))
        if not vseh:
            break
        n += 1
    return n


def _popoldan_termini(db: Session | None, school_id: int | None,
                      ucitelj_ime: str, cfg: dict | None = None) -> list[dict]:
    """Popoldanski termini — uradni četrtki OD 17:30.

    Veljajo za VSE učitelje. Dinamično podaljšanje: ko so vsi trenutni termini
    zasedeni (osnovna 1 ura), se doda po en nov termin — do največ 5 ur od začetka.
    Če sta podana db + school_id, podaljšanje upošteva zasedenost.
    """
    cfg = cfg or _default_cfg()
    term_min = _term_min(cfg)
    zauzeti = (_zasedeni_termini(db, school_id, ucitelj_ime)
               if (db is not None and school_id is not None) else set())
    out = []
    for d in (cfg.get("popoldan_datumi") or POPOLDAN_DATUMI):
        n = _popoldan_odobrenih_termov(d, zauzeti, cfg)
        for i in range(n):
            od = _popoldan_term_od(i, term_min, cfg)
            do = _add_minutes(od, term_min)
            out.append({"datum": d, "ura_od": od, "ura_do": do})
    return out


def _popoldan_termini_maximalni(cfg: dict | None = None) -> list[dict]:
    """VSI možni popoldanski termini (osnova + dodatki do 5 ur od 17:30).

    Za validacijo prijave — sprejmemo tudi pravkar dodane termine (zasedenost
    se medtem lahko spremeni); dvojne prijave prepreči unikat oz. 409.
    """
    cfg = cfg or _default_cfg()
    term_min = _term_min(cfg)
    out = []
    for d in (cfg.get("popoldan_datumi") or POPOLDAN_DATUMI):
        for i in range(_popoldan_max_termov(cfg)):
            od = _popoldan_term_od(i, term_min, cfg)
            out.append({"datum": d, "ura_od": od, "ura_do": _add_minutes(od, term_min)})
    return out


def _naslednji_popoldan(cfg: dict | None = None) -> str | None:
    """Prvi popoldanski datum (četrtek) >= danes — zgornja meja prikaza terminov."""
    cfg = cfg or _default_cfg()
    danes = date.today().isoformat()
    return next((d for d in (cfg.get("popoldan_datumi") or POPOLDAN_DATUMI) if d >= danes), None)


def _konec_termina(p) -> datetime:
    """Konec termina prijave kot datetime (ura_do, sicer ura_od)."""
    ura = p.ura_do or p.ura_od or "00:00"
    h, m = map(int, ura.split(":")[:2])
    return datetime(p.datum.year, p.datum.month, p.datum.day, h, m)


def _prijava_pretekla(p) -> bool:
    """Ali je od konca termina minilo več kot HRAMBA_UR ur (→ avtomatski izbris)."""
    return _konec_termina(p) < datetime.now() - timedelta(hours=HRAMBA_UR)


def _v_oknu(t: dict, cfg: dict | None = None) -> bool:
    """Ali je termin viden staršem: ni starejši od 24 ur in ni po naslednjih
    popoldanskih govorilnih (starejše/bolj oddaljene skrijemo)."""
    h, m = map(int, t["ura_od"].split(":"))
    d = date.fromisoformat(t["datum"])
    zacetek = datetime(d.year, d.month, d.day, h, m)
    if zacetek < datetime.now() - timedelta(hours=TERMIN_MAX_STAROST_UR):
        return False
    naslednji = _naslednji_popoldan(cfg)
    if naslednji is not None and t["datum"] > naslednji:
        return False
    return True


def _vsi_termini_ucitelja(u: dict, cfg: dict | None = None,
                          db: Session | None = None,
                          school_id: int | None = None) -> list[dict]:
    """Vsi termini učitelja (dopoldan + popoldan), ki so TRENUTNO VIDNI
    (okno: 24 ur nazaj → naslednje popoldanske govorilne), urejeni po datumu/uri.

    Popoldanski termini se dinamično podaljšujejo glede na zasedenost (ko so
    podani db + school_id): ko je osnovna ura polna, se doda po en termin
    do največ 5 ur od začetka.
    """
    cfg = cfg or _default_cfg()
    ime = u.get("ime", "") if isinstance(u, dict) else ""
    terms = _dopoldan_termini(u, cfg) + _popoldan_termini(db, school_id, ime, cfg)
    terms = [t for t in terms if _v_oknu(t, cfg)]
    terms.sort(key=lambda t: (t["datum"], t["ura_od"]))
    return terms


def _zasedeni_termini(db: Session, school_id: int | None, ucitelj: str) -> set[tuple]:
    """(datum, ura_od) pari, ki so že prijavljeni — da jih izpustimo iz ponudbe."""
    q = db.query(GovorilnaPrijava).filter(GovorilnaPrijava.ucitelj == ucitelj)
    if school_id is not None:
        q = q.filter(GovorilnaPrijava.school_id == school_id)
    return {(p.datum.isoformat(), p.ura_od) for p in q.all()}


def _prosti_termini(db: Session, school_id: int | None, ucitelj: dict, cfg: dict | None = None) -> list[dict]:
    zauzeti = _zasedeni_termini(db, school_id, ucitelj["ime"])
    prosti = []
    for t in _vsi_termini_ucitelja(ucitelj, cfg, db, school_id):
        if (t["datum"], t["ura_od"]) not in zauzeti:
            prosti.append(t)
    return prosti


def _termini_z_flagom(db: Session, school_id: int | None, ucitelj: dict, cfg: dict | None = None) -> list[dict]:
    """Vsi termini učitelja z bool ``zaseden`` (za javno stran staršev)."""
    zauzeti = _zasedeni_termini(db, school_id, ucitelj["ime"])
    termini = []
    for t in _vsi_termini_ucitelja(ucitelj, cfg, db, school_id):
        vnos = dict(t)
        vnos["zaseden"] = (t["datum"], t["ura_od"]) in zauzeti
        termini.append(vnos)
    return termini


def _termin_obstaja(ucitelj: dict, datum: str, ura_od: str, cfg: dict | None = None) -> bool:
    """Ali je (datum, ura_od) veljaven termin tega učitelja v vidnem oknu?

    Popoldan validiramo proti polnemu oknu (osnova + do 5 ur), da sprejmemo
    tudi pravkar dinamično dodane termine (zasedenost se medtem lahko spremeni).
    """
    cfg = cfg or _default_cfg()
    for t in _dopoldan_termini(ucitelj, cfg) + _popoldan_termini_maximalni(cfg):
        if not _v_oknu(t, cfg):
            continue
        if t["datum"] == datum and t["ura_od"] == ura_od:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Javna stran — prijava starša
# ═══════════════════════════════════════════════════════════════════════

@router.get("/govorilne", response_class=HTMLResponse)
def govorilne_stran(request: Request, db: Session = Depends(get_db)):
    """Javna prijavna stran: izbor učitelja, nato 15-minutni termini."""
    school_id = request_school_id(request) or _default_school_id(db)
    cfg = _load_cfg(db, school_id)
    ucitelji = sorted(
        [{"ime": u["ime"], "ime_priimek": _ime_priimek(u["ime"]),
          "predmet": _opis_ucitelja(u), "prostor": u["prostor"]}
         for u in cfg["ucitelji"]],
        key=lambda x: _priimek(x["ime"]),
    )
    return templates.TemplateResponse(
        request, "govorilne.html",
        {"ucitelji": ucitelji, "termin_minut": _term_min(cfg),
         "hramba_ur": HRAMBA_UR},
    )


@router.get("/govorilne/api/termini")
def govorilne_termini(
    ucitelj: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Prosti termini izbranega učitelja (JSON) — za dinamični UI."""
    school_id = request_school_id(request) or _default_school_id(db)
    cfg = _load_cfg(db, school_id)
    u = _ucitelj_by_ime(ucitelj, cfg["ucitelji"])
    if u is None:
        raise HTTPException(status_code=404, detail="Učitelj ne obstaja")
    return {"ucitelj": u["ime"], "termini": _termini_z_flagom(db, school_id, u, cfg)}


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
    opis = (body.get("opis") or "").strip()

    school_id = request_school_id(request) or _default_school_id(db) or 1
    cfg = _load_cfg(db, school_id)
    u = _ucitelj_by_ime(ucitelj_ime, cfg["ucitelji"])
    if u is None:
        raise HTTPException(status_code=400, detail="Neznan učitelj")
    if not ime_starsa or not email or not otrok:
        raise HTTPException(status_code=400, detail="Izpolnite ime starša, e-naslov in ime otroka")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="E-naslov ni veljaven")
    if not _termin_obstaja(u, datum, ura_od, cfg):
        raise HTTPException(status_code=400, detail="Termin ne obstaja za tega učitelja")

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
        opis=opis,
    )
    db.add(prijava)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ta termin je že zaseden")

    return {
        "ok": True,
        "sporocilo": "Prijava je uspela.",
        "potrdilo": {
            "ucitelj": u["ime"],
            "datum": datum,
            "ura_od": ura_od,
            "ura_do": ura_do,
            "opis": opis,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# Pregled prijav — samo za prijavljene (učitelj svoje, vodstvo/admin vse)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/govorilne/prijave", response_class=HTMLResponse)
def govorilne_prijave_stran(request: Request, db: Session = Depends(get_db)):
    user = get_request_user(request, db)
    if user is None:
        return RedirectResponse(url="/auth/login")

    # Glavni admin (mainadmin, platforma) NE sme videti govorilnih ur v nobenem primeru.
    if is_main_admin(user):
        return RedirectResponse(url="/")

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
        {"prijave": prijave, "role": role, "is_teacher": role == "teacher",
         "is_admin": is_school_admin(user)},
    )


def _pocisti_stare(db: Session) -> int:
    """Izbriši prijave, od katerih je minilo več kot HRAMBA_UR ur (24 ur po dogodku)."""
    starih = [p for p in db.query(GovorilnaPrijava).all() if _prijava_pretekla(p)]
    if starih:
        for p in starih:
            db.delete(p)
        db.commit()
    return len(starih)


@router.post("/govorilne/api/prijava/odstrani")
async def govorilne_prijava_odstrani(
    request: Request,
    db: Session = Depends(get_db),
):
    """Brisanje rezervacije.

    Šolski admin (role=admin) lahko izbriše katerokoli rezervacijo svoje šole.
    Učitelj lahko izbriše samo lastno rezervacijo (tisto na svoje ime).
    Vodstvo in glavni admin lahko rezervacijo le vidijo, ne brišejo je.
    """
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ni prijave")
    school_admin = is_school_admin(user)
    if not school_admin and role_value(user) != "teacher":
        raise HTTPException(status_code=403,
                            detail="Samo šolski admin ali zadevni učitelj lahko briše rezervacije")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    prijava_id = body.get("id")
    if prijava_id is None:
        raise HTTPException(status_code=400, detail="Manjka 'id' prijave")

    school_id = user.school_id or request_school_id(request) or _default_school_id(db)
    q = db.query(GovorilnaPrijava).filter(GovorilnaPrijava.id == prijava_id)
    if school_id is not None:
        q = q.filter(GovorilnaPrijava.school_id == school_id)
    prijava = q.first()
    if prijava is None:
        raise HTTPException(status_code=404, detail="Prijava ne obstaja")

    if not school_admin and prijava.ucitelj != _polno_ime_user(user):
        raise HTTPException(status_code=403,
                            detail="Učitelj lahko izbriše samo svojo rezervacijo")

    db.delete(prijava)
    db.commit()
    return {"ok": True, "id": prijava_id}


# ═══════════════════════════════════════════════════════════════════════
# »Moje govorilne ure« — učitelj v appu vidi/ureja svoj objavljeni urnik
# ═══════════════════════════════════════════════════════════════════════

# Dnevi v tednu (0=pon..4=pet) za prikaz govorilnih ur.
_DANI = ["ponedeljek", "torek", "sreda", "četrtek", "petek"]

# Kdo lahko UREJA vse (popoldan + vse učitelje): šolski admin in vodstvo.
# Glavni admin (mainadmin) govorilnih ur NE SME videti niti urejati.
_EDITOR_ROLES = ("admin", "vodstvo")


def _lahko_ureja_vse(user) -> bool:
    return user is not None and role_value(user) in _EDITOR_ROLES


def _urnik_ucitelja(db: Session, school_id: int | None, u: dict, cfg: dict | None = None,
                    editable: bool = False) -> dict:
    """Pripravi prikaz objavljenega urnika govorilnih ur enega učitelja
    (dopoldanski + popoldanski termin) skupaj z rezervacijami staršev."""
    cfg = cfg or _default_cfg()
    ura_zacetki = _zacetki_za_ucitelja(u, cfg)
    urnik_id = _urnik_ucitelja_za(u)
    urnik_obj = (cfg.get("urniki") or URNIKI).get(urnik_id) or {}
    dopoldan = None
    if not u.get("po_dogovoru") and u.get("dan") is not None and u.get("ura") is not None:
        dan = _DANI[u["dan"]] if 0 <= u["dan"] < 5 else f"dan {u['dan']}"
        dd = _testni_datum(u["dan"], cfg)
        dopoldan = {
            "dan": dan,
            "ura": u["ura"],
            "zacetek": ura_zacetki.get(u["ura"]),
            "datum": dd.isoformat() if dd else "",
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
    naslednji = _naslednji_popoldan(cfg)
    return {
        "ime": u["ime"],
        "ime_priimek": _ime_priimek(u["ime"]),
        "predmet": _opis_ucitelja(u),
        "predmet_raw": (u.get("predmet") or "").strip(),
        "razred": (u.get("razred") or "").strip(),
        "razred_raw": u.get("razred"),
        "dan": u.get("dan"),
        "ura": u.get("ura"),
        "urnik": urnik_id,
        "urnik_label": urnik_obj.get("label") or urnik_id,
        "urnik_max_ura": max(ura_zacetki.keys()),
        "prostor": u.get("prostor") or "",
        "po_dogovoru": bool(u.get("po_dogovoru")),
        "editable": editable,
        "dopoldan": dopoldan,
        # Samo AKTUALNE popoldanske govorilne (naslednji četrtek) — ne celo leto.
        "popoldan_datumi": [naslednji] if naslednji else [],
        "rezervacije": rezervacije,
    }


@router.get("/govorilne/ure", response_class=HTMLResponse)
def govorilne_ure_stran(request: Request, db: Session = Depends(get_db)):
    """Učitelj v appu vidi/ureja svoj objavljeni urnik govorilnih ur in rezervacije.

    - Učitelj: samo svoj objavljeni termin (dan/uro/prostor) + predmet + razred.
    - Vodstvo, šolski admin, glavni admin: pregled + urejanje vseh učiteljev
      in popoldanskih govorilnih ur (kdaj so).
    """
    user = get_request_user(request, db)
    if user is None:
        return RedirectResponse(url="/auth/login")

    # Glavni admin (mainadmin, platforma) NE sme videti govorilnih ur v nobenem primeru.
    if is_main_admin(user):
        return RedirectResponse(url="/")

    role = role_value(user)
    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id
    cfg = _load_cfg(db, school_id)

    # Seznam razredov za spustni seznam (razrednik). Iz nastavitev šole.
    from app.tenancy import get_school_config
    razredi = get_school_config(db, school_id).RAZREDI or []

    if role == "teacher":
        polno_ime = f"{user.first_name} {user.last_name}".strip()
        ucitelj = _ucitelj_by_ime(polno_ime, cfg["ucitelji"])
        prikaz = [_urnik_ucitelja(db, school_id, ucitelj, cfg, editable=True)] if ucitelj else []
    else:
        urejeni = sorted(cfg["ucitelji"], key=lambda u: _priimek(u["ime"]))
        prikaz = [_urnik_ucitelja(db, school_id, u, cfg, editable=True) for u in urejeni]

    return templates.TemplateResponse(
        request, "govorilne_ure.html",
        {"prikaz": prikaz, "role": role, "is_teacher": role == "teacher",
         "is_editor": _lahko_ureja_vse(user),
         "is_admin": is_school_admin(user),
         "razredi": razredi,
         "popoldan_datumi": cfg.get("popoldan_datumi") or POPOLDAN_DATUMI,
         "dopoldan_teden": cfg.get("dopoldan_teden") or GOVORILNE_DOPOLDAN_TEDEN,
         "termin_minut": cfg.get("termin_minut") or TERMIN_MINUT,
         "popoldan_zacetek": cfg.get("popoldan_zacetek") or POPOLDAN_ZACETEK,
         "popoldan_osnovni_min": cfg.get("popoldan_osnovni_min") or POPOLDAN_OSNOVNI_MIN,
         "popoldan_max_ur": cfg.get("popoldan_max_ur") or POPOLDAN_MAX_UR,
         "urniki": cfg.get("urniki") or URNIKI,
         "zvonec_url": cfg.get("zvonec_url") or ZBONJEC_URL},
    )


# ═══════════════════════════════════════════════════════════════════════
# UREJANJE (API) — /govorilne/api/ure/*
# ═══════════════════════════════════════════════════════════════════════

def _polno_ime_user(user) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _poberi_termin_minut(body: dict) -> int | None:
    """Preberi in preveri `termin_minut` iz telesa; None, če ni podan."""
    raw = body.get("termin_minut")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Dolžina termina mora biti število minut")
    if v < 5 or v > 120:
        raise HTTPException(status_code=400, detail="Dolžina termina naj bo med 5 in 120 minut")
    return v


@router.post("/govorilne/api/ure/popoldan")
async def ure_popoldan(request: Request, db: Session = Depends(get_db)):
    """Admin/vodstvo/glavni admin uredi POPOLDANSKE govorilne ure (kdaj so)."""
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ni prijave")
    if not _lahko_ureja_vse(user):
        raise HTTPException(status_code=403, detail="Nimate pravic za urejanje popoldanskih govorilnih ur")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    datumi_raw = body.get("popoldan_datumi")
    if not isinstance(datumi_raw, list):
        raise HTTPException(status_code=400, detail="popoldan_datumi mora biti seznam")

    datumi = []
    for d in datumi_raw:
        s = str(d).strip()
        if not s:
            continue
        try:
            date.fromisoformat(s)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Neveljaven datum: {s}")
        datumi.append(s)

    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id
    cfg = _load_cfg(db, school_id)
    cfg["popoldan_datumi"] = datumi
    termin_minut = _poberi_termin_minut(body)
    if termin_minut is not None:
        cfg["termin_minut"] = termin_minut

    # Začetek popoldanskih ur (nova nastavitev).
    zacetek_raw = body.get("popoldan_zacetek")
    if zacetek_raw is not None and str(zacetek_raw).strip() != "":
        zacetek = str(zacetek_raw).strip()
        try:
            hh, mm = map(int, zacetek.split(":")[:2])
            if not (0 <= hh < 24 and 0 <= mm < 60):
                raise ValueError
            cfg["popoldan_zacetek"] = f"{hh:02d}:{mm:02d}"
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Neveljaven začetek popoldanskih ur (npr. 17:30)")

    # Osnovno trajanje popoldanskih ur v minutah (npr. 60 = osnovna ura).
    osnovni_raw = body.get("popoldan_osnovni_min")
    if osnovni_raw is not None and str(osnovni_raw).strip() != "":
        try:
            v = int(osnovni_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Osnovno trajanje mora biti število minut")
        if v < 15 or v > 180:
            raise HTTPException(status_code=400, detail="Osnovno trajanje naj bo med 15 in 180 minut")
        cfg["popoldan_osnovni_min"] = v

    # Največ koliko ur trajajo popoldanske govorilne (od začetka).
    max_ur_raw = body.get("popoldan_max_ur")
    if max_ur_raw is not None and str(max_ur_raw).strip() != "":
        try:
            v = int(max_ur_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Največ ur mora biti število")
        if v < 1 or v > 8:
            raise HTTPException(status_code=400, detail="Največ ur naj bo med 1 in 8")
        cfg["popoldan_max_ur"] = v

    _save_cfg(db, school_id, cfg)
    return {"ok": True, "popoldan_datumi": datumi,
            "termin_minut": cfg.get("termin_minut"),
            "popoldan_zacetek": cfg.get("popoldan_zacetek"),
            "popoldan_osnovni_min": cfg.get("popoldan_osnovni_min"),
            "popoldan_max_ur": cfg.get("popoldan_max_ur")}


@router.post("/govorilne/api/ure/ucitelj")
async def ure_ucitelj(request: Request, db: Session = Depends(get_db)):
    """Učitelj uredi svoj zapis (dopoldan dan/uro, predmet, razred dropdown).

    Admin/vodstvo/glavni admin lahko uredi poljubnega (obvezno `ime`).
    """
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ni prijave")
    role = role_value(user)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    je_editor = _lahko_ureja_vse(user)
    ime = (body.get("ime") or "").strip()
    if je_editor:
        if not ime:
            raise HTTPException(status_code=400, detail="Manjka 'ime' učitelja")
    else:
        if role != "teacher":
            raise HTTPException(status_code=403, detail="Nimate pravic za urejanje")
        ime = _polno_ime_user(user)

    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id
    cfg = _load_cfg(db, school_id)

    ucitelj = _ucitelj_by_ime(ime, cfg["ucitelji"])
    if ucitelj is None:
        raise HTTPException(status_code=404, detail="Učitelj ni v konfiguraciji")

    # Nova polja, ki jih pišemo v zapis učitelja.
    novi = dict(ucitelj)

    def _opt(key, default=None):
        return body.get(key, default)

    # Predmet (text)
    predmet = (_opt("predmet") or "").strip()
    # Razred (dropdown; prazno = ni razrednik)
    razred = (_opt("razred", "") or "").strip()
    # prostor
    prostor = (_opt("prostor") or "").strip()

    # Dan / ura (dopoldanski termin). Dopustne vrednosti: '' ali dan št. ali None.
    dan_raw = _opt("dan")
    ura_raw = _opt("ura")

    def _parsiraj_dan(v):
        if v is None:
            return None
        s = str(v).strip()
        if s in ("", "null", "None"):
            return None
        if s == "po_dogovoru":
            return None
        try:
            d = int(s)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Neveljaven dan: {s}")
        if d < 0 or d > 4:
            raise HTTPException(status_code=400, detail="Dan mora biti med 0 (pon) in 4 (pet)")
        return d

    # Novo polje: izbrani ŠOLSKI ZVONČNI URNIK (npr. '6-9'). Veljaven id iz URNIKI.
    urnik_raw = _opt("urnik", "")
    urnik = str(urnik_raw or "").strip() or None
    if urnik is not None and urnik not in (_cfg_urniki := (cfg.get("urniki") or URNIKI)):
        raise HTTPException(status_code=400,
                            detail="Neveljaven urnik (izberite 1.-2., 3.-5. ali 6.-9. razred)")

    # Kandidat za max uro: upoštevaj NOVO izbiro urnika, ne stare.
    kandidat = dict(novi)
    if urnik is not None:
        kandidat["urnik"] = urnik

    def _parsiraj_uro(v):
        if v is None:
            return None
        s = str(v).strip()
        if s in ("", "null", "None"):
            return None
        if s == "po_dogovoru":
            return None
        try:
            u = int(s)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Neveljavna ura: {s}")
        # Najvišja ura po učiteljevem (novo) izbranem urniku (npr. 6-9 ima do 8. ure).
        max_ura = _max_solska_ura(kandidat, cfg)
        if u < 1 or u > max_ura:
            raise HTTPException(status_code=400, detail=f"Ura mora biti med 1 in {max_ura}")
        return u

    dan = _parsiraj_dan(dan_raw)
    ura = _parsiraj_uro(ura_raw)

    # Normaliziraj po_dogovoru: če dan/ura prazna → po dogovoru (nima dopoldanskega fiksn.)
    po_dogovoru = not (dan is not None and ura is not None)

    novi["predmet"] = predmet
    novi["razred"] = razred or None
    novi["dan"] = dan
    novi["ura"] = ura
    novi["urnik"] = urnik
    novi["prostor"] = prostor
    novi["po_dogovoru"] = po_dogovoru

    cfg["ucitelji"] = [novi if u2.get("ime") == ucitelj["ime"] else u2
                       for u2 in cfg["ucitelji"]]
    _save_cfg(db, school_id, cfg)
    return {"ok": True, "ucitelj": _urnik_ucitelja(db, school_id, novi, cfg)}


@router.post("/govorilne/api/ure/ucitelj/dodaj")
async def ure_ucitelj_dodaj(request: Request, db: Session = Depends(get_db)):
    """Admin/vodstvo/glavni admin DODA novega učitelja (ime + poljubne)."""
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ni prijave")
    if not _lahko_ureja_vse(user):
        raise HTTPException(status_code=403, detail="Nimate pravic za dodajanje učitelja")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    ime = (body.get("ime") or "").strip()
    if not ime:
        raise HTTPException(status_code=400, detail="Manjka 'ime' učitelja")

    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id
    cfg = _load_cfg(db, school_id)

    if _ucitelj_by_ime(ime, cfg["ucitelji"]) is not None:
        raise HTTPException(status_code=409, detail="Učitelj s tem imenom že obstaja")

    novi = {
        "ime": ime,
        "predmet": (body.get("predmet") or "").strip(),
        "razred": (str(body.get("razred") or "").strip() or None),
        "prostor": (body.get("prostor") or "").strip(),
        "dan": None,
        "ura": None,
        "urnik": None,
        "po_dogovoru": True,
    }

    # Novo polje: izbrani šolski zvončni urnik (npr. '6-9'); veljaven id iz URNIKI.
    urnik_raw = body.get("urnik")
    urnik = str(urnik_raw or "").strip() or None
    if urnik is not None and urnik not in (cfg.get("urniki") or URNIKI):
        raise HTTPException(status_code=400,
                            detail="Neveljaven urnik (izberite 1.-2., 3.-5. ali 6.-9. razred)")
    novi["urnik"] = urnik

    def _parsiraj_dan_v(v):
        if v is None:
            return None
        s = str(v).strip()
        if s in ("", "null", "None", "po_dogovoru"):
            return None
        try:
            d = int(s)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Neveljaven dan: {s}")
        if d < 0 or d > 4:
            raise HTTPException(status_code=400, detail="Dan mora biti med 0 (pon) in 4 (pet)")
        return d

    def _parsiraj_uro_v(v):
        if v is None:
            return None
        s = str(v).strip()
        if s in ("", "null", "None", "po_dogovoru"):
            return None
        try:
            u = int(s)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Neveljavna ura: {s}")
        max_ura = _max_solska_ura(novi, cfg)
        if u < 1 or u > max_ura:
            raise HTTPException(status_code=400, detail=f"Ura mora biti med 1 in {max_ura}")
        return u

    dan = _parsiraj_dan_v(body.get("dan"))
    ura = _parsiraj_uro_v(body.get("ura"))
    novi["dan"] = dan
    novi["ura"] = ura
    novi["po_dogovoru"] = not (dan is not None and ura is not None)

    cfg["ucitelji"].append(novi)
    _save_cfg(db, school_id, cfg)
    return {"ok": True, "ucitelj": _urnik_ucitelja(db, school_id, novi, cfg)}


@router.post("/govorilne/api/ure/ucitelj/odstrani")
async def ure_ucitelj_odstrani(request: Request, db: Session = Depends(get_db)):
    """Admin/vodstvo/glavni admin ODSTRANI učitelja iz seznama."""
    user = get_request_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Ni prijave")
    if not _lahko_ureja_vse(user):
        raise HTTPException(status_code=403, detail="Nimate pravic za odstranjevanje učitelja")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Neveljaven JSON")

    ime = (body.get("ime") or "").strip()
    if not ime:
        raise HTTPException(status_code=400, detail="Manjka 'ime' učitelja")

    school_id = request_school_id(request) or _default_school_id(db)
    if not is_main_admin(user):
        school_id = user.school_id or school_id
    cfg = _load_cfg(db, school_id)

    ucitelj = _ucitelj_by_ime(ime, cfg["ucitelji"])
    if ucitelj is None:
        raise HTTPException(status_code=404, detail="Učitelj ni v konfiguraciji")

    cfg["ucitelji"] = [u2 for u2 in cfg["ucitelji"]
                       if u2.get("ime") != ucitelj["ime"]]
    _save_cfg(db, school_id, cfg)
    # Zbriši tudi obstoječe prijave tega učitelja (da ni nedoslednosti).
    q = db.query(GovorilnaPrijava).filter(GovorilnaPrijava.ucitelj == ucitelj["ime"])
    if school_id is not None:
        q = q.filter(GovorilnaPrijava.school_id == school_id)
    q.delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "ime": ucitelj["ime"]}