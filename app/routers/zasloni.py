# ─────────────────────────────────────────────────────────────────────────
# app/routers/zasloni.py — Šolski digitalni zaslon (nadomeščanja + obvestila)
#
# Namen: Nadomeščanja iz eAsistenta + rotacijo slik/obvestil prikaže kot
# samostojen full-screen zaslon za TV/zaslone v šoli. Zamenjava stare
# PHP verzije (index.php/zasloni.php) v Python/FastAPI.
#
# Pravila:
#   - Endpoint /zasloni in /zasloni/... so JAVNI (brez prijave) — zaslon teče
#     na TV, ki se ne more prijaviti.
#   - Vir nadomeščanj (eAsistent URL) in vse nastavitve se berejo iz
#     šolskih nastavitev (ZASLON_*), konfiguracija šole → .env fallback.
#   - Predpomnilnik nadomeščanj je LOKALEN (/tmp) in se vsak dan ob polnoči
#     samodejno zbriše.
#   - PDF obvestila se samodejno pretvorijo v JPG (ImageMagick / GhostScript).
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import re
import json
import mimetypes
import time
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ZaslonFile
from app.tenancy import (
    _default_school_id,
    get_school_config,
    request_school_id,
)
from app.i18n import t as _ui_t

router = APIRouter(tags=["zasloni"])

# ── Predloge ─────────────────────────────────────────────────────────
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["t"] = _ui_t


# ═══════════════════════════════════════════════════════════════════════
# Konfiguracija zaslona (beremo iz šolskih nastavitev + .env)
# ═══════════════════════════════════════════════════════════════════════

# Defaultni eAsistent vir (isti kot v stari PHP različici).
DEFAULT_ZASLON_URL = (
    "https://urniki.easistent.com/nadomescanja/"
    "d960638bb866d19b58f4e2de616db8eb56e73cfe"
)


def _default_media_dir() -> Path:
    """Mapa za obvestila/slike zaslona (privatna, gitignorirana).

    Znotraj te mape sta podmapl:
      - vec_obvestil/  — dodatna obvestila za naključno rotacijo
      - obvestila/     — (vsebuje logo.jpg privzeto ozadje)
    Ta mapa se monta na URL /zasloni/media/.
    """
    base = Path(os.getenv("ZASLON_MEDIA_DIR") or
                os.path.join(os.path.dirname(__file__), "..", "..", "zasloni_media"))
    return Path(base).resolve()


def _zasloni_settings(request: Request, db: Session) -> dict:
    """Zbere nastavitve zaslona (če šola obstaja → njene ZASLON_* vrednosti).

    Šolo določimo iz URL-aliasa (/nadomescanja_<slug>); za javno kanonično pot
    (brez prijave) pademo na privzeto šolo. Če ni šole, uporabimo .env fallback
    (SchoolConfig(None, {}) → env_default_settings).
    """
    # Šolo izberemo iz URL-aliasa (vsaka šola dobi svojo /nadomescanja_<slug>
    # pot, ki pokaže NJENE nastavitve). Če ni aliasa → privzeta šola.
    sid = request_school_id(request)
    if sid is None:
        sid = _default_school_id(db)
    config = get_school_config(db, sid)

    def b(key: str, fallback: bool) -> bool:
        v = config.get_str(key, "").strip().lower()
        return v in ("1", "true", "yes", "on") if v else fallback

    def i(key: str, fallback: int) -> int:
        return config.get_int(key, fallback)

    def f(key: str, fallback: float) -> float:
        v = config.get_str(key, "").strip()
        try:
            return float(v) if v else fallback
        except (TypeError, ValueError):
            return fallback

    media_dir = _default_media_dir()
    # Aktivna obvestila (ZASLON_OBVESTILA): JSON seznam imen v VRSTNEM redu.
    obvestila = []
    try:
        raw_obv = config.get_str("ZASLON_OBVESTILA", "").strip()
        if raw_obv:
            parsed = json.loads(raw_obv)
            if isinstance(parsed, list):
                obvestila = [str(x) for x in parsed]
    except (TypeError, ValueError):
        obvestila = []
    # Tekstovna obvestila (ZASLON_OBVESTILA_TEKST): JSON seznam besedil, ki jih
    # admin doda v UI (največ 5). Vrtijo se na zaslonu skupaj s slikovnimi.
    obvestila_tekst = []
    try:
        raw_txt = config.get_str("ZASLON_OBVESTILA_TEKST", "").strip()
        if raw_txt:
            parsed_txt = json.loads(raw_txt)
            if isinstance(parsed_txt, list):
                obvestila_tekst = [str(x).strip() for x in parsed_txt if str(x).strip()][:5]
    except (TypeError, ValueError):
        obvestila_tekst = []
    return {
        "url": config.get_str("ZASLON_URL", DEFAULT_ZASLON_URL),
        "pokazi_nadomescanja": b("ZASLON_POKAZI_NADOMESCANJA", True),
        "cas_obvestila": i("ZASLON_CAS_OBVESTILA", 5),
        "min_cas_tabele": i("ZASLON_MIN_CAS_TABELE", 2),
        "hitrost_drsenja": f("ZASLON_HITROST_DRSENJA", 1.2),
        "time_zone": config.get_str("ZASLON_TIME_ZONE", "Europe/Ljubljana"),
        "osvezi_at": config.get_str("ZASLON_OSVEZI_AT", ""),
        "school_id": sid,
        "obvestila": obvestila,
        "obvestila_tekst": obvestila_tekst,
        "media_dir": media_dir,
        "vec_obvestil": media_dir / "vec_obvestil",
        "logo_path": "obvestila/logo.jpg",
        "school_name": config.get_str("SCHOOL_NAME", "OŠ Toneta Čufarja"),
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. Samodejno brisanje predpomnilnika ob polnoči
# ═══════════════════════════════════════════════════════════════════════

CACHE_FILE = "/tmp/nadomescanja_razredi_cache.html"
CACHE_STAMP = "/tmp/nadomescanja_cache_time.txt"


def _clear_cache_if_new_day() -> None:
    """Prvi klic v novem dnevu v dnevu počisti predpomnilnik nadomeščanj."""
    danes = time.strftime("%Y-%m-%d")
    zadnji = ""
    try:
        with open(CACHE_STAMP, "r", encoding="utf-8") as fh:
            zadnji = fh.read().strip()
    except OSError:
        pass
    if zadnji != danes:
        try:
            os.unlink(CACHE_FILE)
        except OSError:
            pass
        try:
            with open(CACHE_STAMP, "w", encoding="utf-8") as fh:
                fh.write(danes)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════
# 2. Zbiranje IP-jev za ?status
# ═══════════════════════════════════════════════════════════════════════

IP_MONITOR_FILE = "/tmp/ekrani_ips.json"


def _log_ip(request: Request) -> None:
    """Zabeleži IP + user-agent (za /zasloni/status)."""
    if request.query_params.get("status"):
        return
    ipji = {}
    try:
        with open(IP_MONITOR_FILE, "r", encoding="utf-8") as fh:
            ipji = json.load(fh)
        if not isinstance(ipji, dict):
            ipji = {}
    except (OSError, ValueError):
        ipji = {}
    ipji[request.client.host if request.client else "unknown"] = {
        "time": time.time(),
        "ua": request.headers.get("user-agent", "unknown"),
    }
    if len(ipji) > 100:
        ipji = dict(list(ipji.items())[-100:])
    try:
        os.makedirs(os.path.dirname(IP_MONITOR_FILE), exist_ok=True)
        with open(IP_MONITOR_FILE, "w", encoding="utf-8") as fh:
            json.dump(ipji, fh)
    except OSError:
        pass


def _nadomescanja_html(url: str) -> str | None:
    """Potegne nadomeščanja iz eAsistenta (javni URL). Vrne HTML ali None."""
    import requests
    try:
        resp = requests.get(
            url,
            timeout=15,
            allow_redirects=True,
            verify=False,  # enako kot PHP CURLOPT_SSL_VERIFYPEER=false
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _izrezi_prvo_tabelo(html: str) -> str | None:
    """Iz HTML izreže tabelo z nadomeščanji po razredih."""
    m = re.search(
        r'Nadomeščanja po razredih</div>.*?<div class="card-content">(.*?)</div>\s*</div>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        content = m.group(1)
        tm = re.search(r'<table class="table_list"[^>]*>.*?</table>', content, re.DOTALL | re.IGNORECASE)
        if tm:
            return tm.group(0)
    tm = re.search(r'<th>Razred</th>.*?</table>', html, re.DOTALL | re.IGNORECASE)
    if tm:
        return '<table class="table_list">' + tm.group(0) + "</table>"
    return None


def _danes_easistent_datum(time_zone: str) -> str:
    """Današnji datum (YYYY-MM-DD) v šolskem časovnem pasu, kot ga eAsistent
    pričakuje v AJAX seznam URL-ju."""
    try:
        tz = ZoneInfo(time_zone or "Europe/Ljubljana")
    except Exception:
        tz = ZoneInfo("Europe/Ljubljana")
    return datetime.now(tz).strftime("%Y-%m-%d")


def _tabela_iz_ajax(url: str, time_zone: str) -> str | None:
    """eAsistent (od 10/2026) glavne nadomeščanjske tabele NE vključi v inicialni
    HTML — naloži jo prek AJAX GET /nadomescanja/{hash}/{Datum}/seznam, ki odda
    JSON {data: "<html tabela>"}. Ta funkcija požene ta URL in vrne tabelo.

    Če eAsistent pobere datum iz datepickerja — mi pošljemo današnji datum po
    šolskem času; eAsistent vrne tabelo za ta dan (ali '' za 'ni nadomeščanj')."""
    import requests
    dan = _danes_easistent_datum(time_zone)
    base = url.rstrip("/")
    # URL je npr. https://urniki.easistent.com/nadomescanja/<hash> → dodamo /<dan>/seznam
    seznam_url = f"{base}/{dan}/seznam"
    try:
        resp = requests.get(
            seznam_url,
            timeout=20,
            allow_redirects=True,
            verify=False,  # enako kot PHP CURLOPT_SSL_VERIFYPEER=false
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, str) or not data.strip():
        return None
    if "nadomeščanj" in data.lower() and "<table" not in data:
        # eAsistent: "Za ta dan ni nadomeščanj." → brez tabele
        return None
    return _izrezi_prvo_tabelo(data)


def _pridobi_tabelo(url: str, time_zone: str = "Europe/Ljubljana") -> str | None:
    """Sveža tabela iz eAsistenta; uspeh shrani v predpomnilnik.

    Primarno poskusi eAsistent AJAX seznam endpoint (tabela ni več v inicialnem
    HTML), fallback na stari parse inicialnega HTML-ja."""
    tabela = _tabela_iz_ajax(url, time_zone)
    if not tabela:
        # Fallback: stari način (če AJAX pade ali se eAsistent vrne na staro obliko).
        html = _nadomescanja_html(url)
        if html:
            tabela = _izrezi_prvo_tabelo(html)
    if not tabela:
        return None
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            fh.write(tabela)
    except OSError:
        pass
    return tabela


# ═══════════════════════════════════════════════════════════════════════
# 3. PDF → JPG
# ═══════════════════════════════════════════════════════════════════════

def _pretvori_pdf_v_sliko(pdf_path: Path) -> Path | None:
    """Pretvori prvo stran PDF-ja v JPG (ImageMagick → GhostScript fallback)."""
    jpg = pdf_path.with_suffix(".jpg")
    if jpg.exists() and jpg.stat().st_mtime >= pdf_path.stat().st_mtime:
        return jpg
    # ImageMagick convert
    try:
        r = subprocess.run(
            ['convert', f'"{pdf_path}"[0]', "-quality", "85", "-resize", "1920x1080", f'"{jpg}"'],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and jpg.exists():
            return jpg
    except Exception:
        pass
    # GhostScript fallback
    try:
        r = subprocess.run(
            ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-r150",
             "-dFirstPage=1", "-dLastPage=1", f"-sOutputFile={jpg}", str(pdf_path)],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and jpg.exists():
            return jpg
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════
# 4. Naključna slika iz mape vec_obvestil
# ═══════════════════════════════════════════════════════════════════════

def _nakljucna_slika(vec_dir: Path) -> str | None:
    """Vrni URL relativni (za /zasloni/media/) naključne slike ali None."""
    if not vec_dir.is_dir():
        return None
    files = [f for f in vec_dir.iterdir() if f.is_file() and
             f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}]
    if not files:
        return None
    izbrana = files[int(time.time() * 1000) % len(files)]
    ext = izbrana.suffix.lower()
    if ext == ".pdf":
        jpg = _pretvori_pdf_v_sliko(izbrana)
        if jpg and jpg.exists():
            return f"vec_obvestil/{jpg.name}"
        return None
    return f"vec_obvestil/{izbrana.name}"


# ═══════════════════════════════════════════════════════════════════════
# 4b. Aktivna obvestila (po vrsti) — za /zasloni/obvestila
# ═══════════════════════════════════════════════════════════════════════

_ZASLON_DISK_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}


def _pdf_to_jpg_bytes(pdf_bytes: bytes, scale: float = 2.0) -> bytes:
    """Prva stran PDF-ja → JPG bajti (pypdfium2 + Pillow).

    Uporabi se pri nalaganju obvestila: PDF se pretvori v sliko in v sistem
    se shrani SAMO ta slika (zasede 1 polje obvestila).
    """
    import io
    import pypdfium2 as pdfium
    from PIL import Image
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[0]
        pil = page.render(scale=scale).to_pil().convert("RGB")
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=85)
        return buf.getvalue()
    finally:
        doc.close()


def _razpolozljiva_obvestila(db: Session, sid: int | None, media_dir: Path) -> list[str]:
    """Imena razpoložljivih obvestil (datotek v vec_obvestil/) za šolo.

    Vir so DB vrstice (ZaslonFile — naložena obvestila). Prvič, ko šola
    še nima nobene, se diskovna obvestila (vgrajena v sliko) prenesejo v
    DB — od takrat je DB edini vir, da izbrisana obvestila ob redeployu
    ne oživijo.
    """
    if sid is None:
        return []
    rows = db.query(ZaslonFile.filename).filter(ZaslonFile.school_id == sid).all()
    if rows:
        return sorted(r[0] for r in rows)
    names = []
    if media_dir.is_dir():
        for f in sorted(media_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in _ZASLON_DISK_EXT:
                names.append(f.name)
                try:
                    db.add(ZaslonFile(school_id=sid, filename=f.name, data=f.read_bytes()))
                except OSError:
                    pass
    db.commit()
    return names


def _aktivna_obvestila(settings: dict, db: Session) -> list[str]:
    """Vrni relativne URL-je aktivnih obvestil PO VRSTI (ne naključno).

    Šola v nastavitvah (ZASLON_OBVESTILA, JSON seznam imen) določi katera
    obvestila so aktivna in v kakšnem vrstnem redu se prikazujejo. Če ni
    podano (prazno), se uporabijo VSA razpoložljiva obvestila po abecedi.
    """
    vec_dir: Path = settings["vec_obvestil"]
    razpoložljiva = _razpolozljiva_obvestila(db, settings.get("school_id"), vec_dir)
    if not razpoložljiva:
        return []

    izbrana_raw = settings.get("obvestila")
    if not izbrana_raw:
        return [f"vec_obvestil/{n}" for n in razpoložljiva]

    urlji = []
    for n in izbrana_raw:
        n = (n or "").strip()
        if not n or n not in razpoložljiva:
            continue
        if n.endswith(".pdf"):
            jpg = _pretvori_pdf_v_sliko(vec_dir / n)
            if jpg and jpg.exists():
                urlji.append(f"vec_obvestil/{jpg.name}")
        else:
            urlji.append(f"vec_obvestil/{n}")
    return urlji


# ═══════════════════════════════════════════════════════════════════════
# 5. Endpoints
# ═══════════════════════════════════════════════════════════════════════

@router.get("/zasloni/status", response_class=PlainTextResponse)
def zasloni_status(request: Request, db: Session = Depends(get_db)):
    """Prikaže stanje: aktivni IP-ji + ali so nadomeščanja vklopljena."""
    ipji = {}
    try:
        with open(IP_MONITOR_FILE, "r", encoding="utf-8") as fh:
            ipji = json.load(fh)
        if not isinstance(ipji, dict):
            ipji = {}
    except (OSError, ValueError):
        ipji = {}

    trenutni = time.time()
    aktivni, neaktivni = [], []
    for ip, data in ipji.items():
        ts = data["time"] if isinstance(data, dict) else data
        ua = (data.get("ua") or "unknown") if isinstance(data, dict) else "unknown"
        razlika = trenutni - ts
        line = f"{ip} (pred {int(razlika)} s) - {ua}"
        (aktivni if razlika < 300 else neaktivni).append(line)

    settings = _zasloni_settings(request, db)
    lines = [
        "=== AKTIVNI IP-ji (zadnjih 5 min) ===",
        "\n".join(aktivni) if aktivni else "(ni aktivnih)",
        "",
        "=== NEAKTIVNI IP-ji ===",
        "\n".join(neaktivni) if neaktivni else "(ni neaktivnih)",
        "",
        f"Skupaj zabeleženih IP-jev: {len(ipji)}",
        "",
        "=== STANJE NADOMEŠČANJ ===",
        ("NADOMEŠČANJA SO VKLOPLJENA" if settings["pokazi_nadomescanja"]
         else "NADOMEŠČANJA SO IZKLOPLJENA (samo slika)"),
    ]
    return "\n".join(lines) + "\n"


@router.get("/zasloni/random_image", response_class=JSONResponse)
def zasloni_random_image(request: Request, db: Session = Depends(get_db)):
    """Vrne naključno sliko (JSON {slika: ...}) za JavaScript rotacijo.

    Združljivost: če so obvestila (ZASLON_OBVESTILA) določena po vrsti,
    vrne prvo aktivno; sicer naključno. Večina brskalnikov uporablja
    /zasloni/obvestila (urejen seznam), ta endpoint pa ostaja za nazaj.
    """
    settings = _zasloni_settings(request, db)
    razpoložljiva = _razpolozljiva_obvestila(db, settings["school_id"], settings["vec_obvestil"])
    if razpoložljiva:
        izbrana = razpoložljiva[int(time.time() * 1000) % len(razpoložljiva)]
        slika = f"vec_obvestil/{izbrana}"
    else:
        slika = settings["logo_path"]
    return {"slika": slika}


@router.get("/zasloni/obvestila", response_class=JSONResponse)
def zasloni_obvestila(request: Request, db: Session = Depends(get_db)):
    """Urejen seznam aktivnih obvestil (JSON {obvestila: [...]}).

    Uporabi ga JavaScript za rotacijo PO VRSTI: vsako obvestilo se prikaže
    v vrstnem redu, kot ga določi šola v ZASLON_OBVESTILA (v nasprotnem
    primeru vsa iz vec_obvestil po abecedi). Brez aktivnih → privzeti logo.
    """
    settings = _zasloni_settings(request, db)
    obvestila = _aktivna_obvestila(settings, db)  # relativni URL-ji slik (str)
    seznam = [{"type": "image", "src": u, "text": None} for u in obvestila]
    obvestila_tekst = settings.get("obvestila_tekst") or []
    seznam += [{"type": "text", "src": None, "text": t} for t in obvestila_tekst]
    if not seznam:
        seznam = [{"type": "image", "src": settings["logo_path"], "text": None}]
    return {"obvestila": seznam}


@router.get("/zasloni/osvezi_at", response_class=JSONResponse)
def zasloni_osvezi_at(request: Request, db: Session = Depends(get_db)):
    """Vrni trenutno oznako osvežitve — zasloni jo pollajo in ob spremembi reloadajo.

    Gumb »Osveži vse naprave« (šolski admin) spremeni ZASLON_OSVEZI_AT;
    vsi zasloni primerjajo to vrednost z vgrajeno v strani in se osvežijo.
    """
    settings = _zasloni_settings(request, db)
    return {"osvezi_at": settings.get("osvezi_at", "")}


@router.get("/zasloni/media/vec_obvestil/{filename}")
def zasloni_media_vec(filename: str, request: Request, db: Session = Depends(get_db)):
    """Servira obvestilo: najprej iz DB (naloženo), sicer z diska (vgrajeno).

    Specifična ruta stoji pred StaticFiles mountom (/zasloni/media), zato
    prevlada za vse datoteke v vec_obvestil/.
    """
    if "/" in filename or filename in (".", ".."):
        raise HTTPException(status_code=404, detail="Datoteka ne obstaja")
    sid = request_school_id(request) or _default_school_id(db)
    row = None
    if sid is not None:
        row = db.query(ZaslonFile).filter(
            ZaslonFile.school_id == sid, ZaslonFile.filename == filename
        ).first()
    if row:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Response(content=bytes(row.data), media_type=mime)
    p = _default_media_dir() / "vec_obvestil" / filename
    if p.is_file():
        return FileResponse(p)
    raise HTTPException(status_code=404, detail="Datoteka ne obstaja")


@router.get("/zasloni", response_class=HTMLResponse)
def zasloni_praznos(request: Request, db: Session = Depends(get_db)):
    """Glavni prikaz (jamski URL) — full-screen zaslon z nadomeščanji + slikami."""
    _log_ip(request)
    _clear_cache_if_new_day()

    settings = _zasloni_settings(request, db)
    tabela = None

    if settings["pokazi_nadomescanja"]:
        sveza = _pridobi_tabelo(settings["url"], settings.get("time_zone", "Europe/Ljubljana"))
        if sveza:
            tabela = sveza
        else:
            # Če eAsistent ni dosegljiv, izbriši predpomnilnik (sveže jutri).
            try:
                os.unlink(CACHE_FILE)
            except OSError:
                pass
            tabela = None
        if tabela:
            tabela = tabela.replace(
                '<strong class="text-danger">odpade</strong>',
                '<strong class="text-danger" style="text-decoration:line-through;">odpade</strong>',
            )

    # Začetna slika: prva aktivna po vrsti, sicer privzeti logo.
    obvestila = _aktivna_obvestila(settings, db)
    obvestilo_path = obvestila[0] if obvestila else settings["logo_path"]

    return templates.TemplateResponse("zasloni.html", {
        "request": request,
        "pokazi_nadomescanja": settings["pokazi_nadomescanja"],
        "cas_obvestila": settings["cas_obvestila"],
        "min_cas_tabele": settings["min_cas_tabele"],
        "hitrost_drsenja": settings["hitrost_drsenja"],
        "time_zone": settings["time_zone"],
        "osvezi_at": settings["osvezi_at"],
        "tabela": tabela,
        "obvestilo_path": obvestilo_path,
        "obvestila": obvestila,
        "school_name": settings["school_name"],
    })