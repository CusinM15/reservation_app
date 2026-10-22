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
import time
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
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
    return {
        "url": config.get_str("ZASLON_URL", DEFAULT_ZASLON_URL),
        "pokazi_nadomescanja": b("ZASLON_POKAZI_NADOMESCANJA", True),
        "cas_obvestila": i("ZASLON_CAS_OBVESTILA", 5),
        "min_cas_tabele": i("ZASLON_MIN_CAS_TABELE", 2),
        "hitrost_drsenja": f("ZASLON_HITROST_DRSENJA", 1.2),
        "obvestila": obvestila,
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


def _pridobi_tabelo(url: str) -> str | None:
    """Sveža tabela iz eAsistenta; uspeh shrani v predpomnilnik."""
    html = _nadomescanja_html(url)
    if not html:
        return None
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

def _aktivna_obvestila(settings: dict) -> list[str]:
    """Vrni relativne URL-je aktivnih obvestil PO VRSTI (ne naključno).

    Šola v nastavitvah (ZASLON_OBVESTILA, JSON seznam imen) določi katera
    obvestila so aktivna in v kakšnem vrstnem redu se prikazujejo. Če ni
    podano (prazno), se uporabijo VSA obvestila iz vec_obvestil/ po abecedi.
    """
    vec_dir: Path = settings["vec_obvestil"]
    if not vec_dir.is_dir():
        return []
    razpoložljiva = sorted(
        f.name for f in vec_dir.iterdir()
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
    )
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
    slika = _nakljucna_slika(settings["vec_obvestil"])
    if not slika:
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
    obvestila = _aktivna_obvestila(settings)
    if not obvestila:
        obvestila = [settings["logo_path"]]
    return {"obvestila": obvestila}


@router.get("/zasloni", response_class=HTMLResponse)
def zasloni_praznos(request: Request, db: Session = Depends(get_db)):
    """Glavni prikaz (jamski URL) — full-screen zaslon z nadomeščanji + slikami."""
    _log_ip(request)
    _clear_cache_if_new_day()

    settings = _zasloni_settings(request, db)
    tabela = None

    if settings["pokazi_nadomescanja"]:
        sveza = _pridobi_tabelo(settings["url"])
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
    obvestila = _aktivna_obvestila(settings)
    obvestilo_path = obvestila[0] if obvestila else settings["logo_path"]

    return templates.TemplateResponse("zasloni.html", {
        "request": request,
        "pokazi_nadomescanja": settings["pokazi_nadomescanja"],
        "cas_obvestila": settings["cas_obvestila"],
        "min_cas_tabele": settings["min_cas_tabele"],
        "hitrost_drsenja": settings["hitrost_drsenja"],
        "tabela": tabela,
        "obvestilo_path": obvestilo_path,
        "obvestila": obvestila,
        "school_name": settings["school_name"],
    })