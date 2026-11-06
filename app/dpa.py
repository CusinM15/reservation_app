# ─────────────────────────────────────────────────────────────────────────
# app/dpa.py — Pogodba o obdelavi osebnih podatkov (DPA)
#
# Šola izpolni svoje podatke (sekcija DPA v nastavitvah), klikne »Podpiši«
# in aplikacija izdela PDF, podpisan z OBEMA stranema:
#   - šola: navadni e-podpis (prijavljeni admin, ime, datum, hash),
#   - ponudnik: samodejno na podlagi pooblastila (podatki iz ERACUN_IZDAJATELJ_*,
#     istega vira kot za e-račune).
# Podpisan PDF se shrani per-šola (dpa_agreements); /docs/html/dpa ga prikaže
# z gumboma Prenesi in Ponastavi.
# ─────────────────────────────────────────────────────────────────────────

import hashlib
import html as html_mod
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.app_settings import get_app_setting
from app.models import DpaAgreement, School, User

DPA_VERSION = "1.0"

DPA_KEYS = ["DPA_NASLOV", "DPA_DAVCNA", "DPA_MATICNA", "DPA_ZASTOPNIK", "DPA_FUNKCIJA"]

_PROVIDER_KEYS = {
    "naziv": "ERACUN_IZDAJATELJ_NAZIV",
    "naslov": "ERACUN_IZDAJATELJ_NASLOV",
    "davcna": "ERACUN_IZDAJATELJ_DAVCMA",
    "maticna": "ERACUN_IZDAJATELJ_MATICNA",
    "email": "ERACUN_IZDAJATELJ_EMAIL",
}


def provider_data(db: Session) -> dict:
    """Podatki ponudnika — isti vir kot za e-račune (ERACUN_IZDAJATELJ_*)."""
    d = {}
    for key, setting in _PROVIDER_KEYS.items():
        d[key] = (get_app_setting(db, setting, "") or "").strip()
    return d


def school_dpa_data(db: Session, school: School) -> dict:
    from app.tenancy import get_school_settings_map

    d = {"ime": school.name}
    mapa = get_school_settings_map(db, school.id) or {}
    for key in DPA_KEYS:
        d[key] = (mapa.get(key, "") or "").strip()
    return d


def provider_complete(provider: dict) -> bool:
    return bool(provider.get("naziv") and provider.get("naslov"))


def school_complete(sdata: dict) -> bool:
    return bool(sdata.get("ime") and sdata.get("DPA_NASLOV") and sdata.get("DPA_ZASTOPNIK")
                and sdata.get("DPA_FUNKCIJA"))


def get_agreement(db: Session, school_id: int) -> DpaAgreement | None:
    return db.query(DpaAgreement).filter(DpaAgreement.school_id == school_id).first()


def _row(label: str, value: str) -> str:
    return (f'<tr><td style="width:200px;font-weight:600;padding:5px 8px;'
            f'border:1px solid #999;vertical-align:top;">{html_mod.escape(label)}</td>'
            f'<td style="padding:5px 8px;border:1px solid #999;">{html_mod.escape(value or "—")}</td></tr>')


def dpa_html(school_name: str, sdata: dict, provider: dict,
             school_sig: str, provider_sig: str, version: str = DPA_VERSION) -> str:
    """Celotna DPA kot HTML (vhod za weasyprint)."""
    upr = _row("Naziv šole", school_name)
    upr += _row("Naslov", sdata.get("DPA_NASLOV", ""))
    upr += _row("Davčna številka", sdata.get("DPA_DAVCNA", ""))
    upr += _row("Matična številka", sdata.get("DPA_MATICNA", ""))
    upr += _row("Ime in priimek zastopnika", sdata.get("DPA_ZASTOPNIK", ""))
    upr += _row("Funkcija", sdata.get("DPA_FUNKCIJA", ""))
    upr += _row("E-pošta administratorja", sdata.get("DPA_EMAIL", ""))

    obd = _row("Naziv", provider.get("naziv", ""))
    obd += _row("Naslov", provider.get("naslov", ""))
    obd += _row("Davčna številka", provider.get("davcna", ""))
    obd += _row("Matična številka", provider.get("maticna", ""))
    obd += _row("E-pošta", provider.get("email", ""))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 2cm; }}
  body {{ font-family: "DejaVu Sans", sans-serif; font-size: 10.5pt; line-height: 1.5; color: #222; }}
  h1 {{ font-size: 15pt; color: #1a1a2e; margin-bottom: 2px; }}
  h2 {{ font-size: 12pt; color: #1a1a2e; border-bottom: 1.5px solid #4a6cf7; padding-bottom: 3px; margin-top: 18px; }}
  .sub {{ color: #555; font-size: 9.5pt; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  td {{ font-size: 10pt; }}
  .sig {{ margin-top: 26px; }}
  .sig td {{ border: 1px solid #999; padding: 6px 10px; height: 70px; vertical-align: top; }}
  .hash {{ font-size: 8pt; color: #777; word-break: break-all; }}
  ol {{ padding-left: 22px; }}
  li {{ margin-bottom: 5px; }}
</style>
</head>
<body>
  <h1>Pogodba o obdelavi osebnih podatkov (DPA)</h1>
  <p class="sub">Različica: {html_mod.escape(version)} · Sklenjena: {html_mod.escape(school_sig)}</p>

  <p>Ta pogodba o obdelavi osebnih podatkov (v nadaljevanju: DPA) je sklenjena med:</p>
  <table>
    <tr><td style="border:1px solid #999;padding:8px 10px;">
      <b>Upravljavec (šola):</b>{upr}
    </td></tr>
    <tr><td style="border:1px solid #999;padding:8px 10px;border-top:none;">
      <b>Obdelovalec (ponudnik):</b>{obd}
    </td></tr>
  </table>

  <h2>1. Predmet in namen obdelave</h2>
  <p>Ponudnik obdeluje osebne podatke izključno za zagotavljanje delovanja šolske aplikacije Reservation App
  (rezervacije prostorov in opreme, dnevi dejavnosti, napoved ocenjevanj, prijave na govorilne ure,
  digitalni zaslon z nadomeščanji) — po navodilih šole in v njenem imenu, kot upravljavke podatkov.</p>

  <h2>2. Trajanje</h2>
  <p>Za čas trajanja naročniškega razmerja oz. do prenehanja ali odpovedi te pogodbe.</p>

  <h2>3. Vrste podatkov in kategorije posameznikov</h2>
  <ol>
    <li>Učitelji, vodstvo in administratorji: ime, priimek, e-pošta, uporabniško ime, vloga, podatki o govorilnih urah.</li>
    <li>Učenci: ime, priimek, razred (če jih šola vnese v aplikacijo).</li>
    <li>Starši ali zakoniti zastopniki: ime, priimek, e-pošta, ime otroka in razred (pri prijavah na govorilne ure).</li>
    <li>Podatki o rezervacijah, ocenjevanjih, dnevih dejavnosti in nadomeščanjih.</li>
    <li>Tehnični podatki: dnevniki dostopov, IP-naslovi, čas prijave.</li>
  </ol>

  <h2>4. Obveznosti ponudnika</h2>
  <ol>
    <li>Osebne podatke obdeluje izključno po dokumentiranih navodilih šole.</li>
    <li>Zagotavlja zaupnost — osebe, ki obdelujejo podatke, so k zaupnosti zavezane.</li>
    <li>Izvaja varnostne ukrepe iz 5. člena.</li>
    <li>Šoli pomaga pri uveljavljanju pravic posameznikov (dostop, popravek, izbris, omejitev, prenosljivost).</li>
    <li>Ob vdoru v osebne podatke o tem obvesti šolo brez nepotrebnega odlašanja, najpozneje v 72 urah.</li>
    <li>Ne prenaša osebnih podatkov v tretje države brez ustreznih zaščitnih ukrepov.</li>
  </ol>

  <h2>5. Varnostni ukrepi</h2>
  <ol>
    <li>Dostop do podatkov samo po načelu najmanjših pravic (ločeni uporabniki in vloge).</li>
    <li>Gesla shranjena zgoščeno; seje podpisane in časovno omejene.</li>
    <li>Šifriran prenos podatkov (HTTPS).</li>
    <li>Dnevnik sprememb (avditni dnevnik).</li>
    <li>Redne varnostne kopije — za njihovo izvedbo poskrbi šolski administrator (v skladu s pogoji uporabe, 5.1).</li>
    <li>Fizična in omrežna zaščita strežnikov, na katerih aplikacija deluje.</li>
  </ol>

  <h2>6. Podizvajalci</h2>
  <ol>
    <li>Gostovanje strežnika in infrastruktura: po podatkih ponudnika (npr. Contabo GmbH).</li>
    <li>E-poštni strežniki: po nastavitvah šole (SMTP).</li>
    <li>Izdajanje e-računov: v skladu s pogoji uporabe.</li>
  </ol>
  <p>Ponudnik šolo obvesti o spremembah podizvajalcev; šola jim lahko obrazloženo ugovarja.</p>

  <h2>7. Pravice posameznikov</h2>
  <p>Ponudnik šoli pomaga pri odgovoru na zahteve posameznikov. Posameznikom ne odgovarja neposredno,
  razen s pooblastilom šole.</p>

  <h2>8. Prenehanje</h2>
  <p>Ob prenehanju naročniškega razmerja ponudnik po navodilih šole podatke vrne (izvoz) ali izbriše,
  razen če zakon zahteva hrambo. Ponudnik na zahtevo šole izda pisni zapis o izbrisu.</p>

  <h2>9. Revizija in dokazila</h2>
  <p>Šola ima pravico do informacij o varnostnih ukrepih. Neposredna revizija je možna po predhodnem
  dogovoru, ob najavi in brez ogrožanja varnosti drugih šol.</p>

  <h2>10. Odgovornost</h2>
  <p>Ponudnik odgovarja za obdelavo v okviru svojih obveznosti po tej pogodbi. Šola je odgovorna za
  zakonitost vnesenih podatkov in vsebino.</p>

  <h2>11. Veljavnost in podpis</h2>
  <p>Pogodba je sklenjena z elektronskim podpisom obeh strank v aplikaciji (e-podpis zadošča skladno
  z eIDAS in ZEP). Velja od trenutka podpisa.</p>

  <table class="sig">
    <tr>
      <td style="width:50%;">
        <b>Upravljavec (šola)</b><br>
        {html_mod.escape(school_name)}<br><br>
        Ime in funkcija: {html_mod.escape(sdata.get('DPA_ZASTOPNIK', ''))}, {html_mod.escape(sdata.get('DPA_FUNKCIJA', ''))}<br>
        Datum: {html_mod.escape(school_sig)}<br><br>
        <i>Podpisano elektronsko v aplikaciji (Reservation App).</i>
      </td>
      <td style="width:50%;">
        <b>Obdelovalec (ponudnik)</b><br>
        {html_mod.escape(provider.get('naziv', ''))}<br><br>
        Datum: {html_mod.escape(provider_sig)}<br><br>
        <i>Podpisano samodejno na podlagi pooblastila ponudnika v aplikaciji Reservation App.</i>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_dpa_pdf(school: School, sdata: dict, provider: dict,
                  school_sig: str, provider_sig: str, version: str = DPA_VERSION) -> bytes:
    from weasyprint import HTML as WP_HTML

    html_doc = dpa_html(school.name, sdata, provider, school_sig, provider_sig, version)
    return WP_HTML(string=html_doc).write_pdf()


def sign_dpa(db: Session, school: School, user: User) -> DpaAgreement:
    """Izdelaj in shrani podpisano DPA (obstojeca se nadomesti)."""
    sdata = school_dpa_data(db, school)
    provider = provider_data(db)
    if not school_complete(sdata):
        raise ValueError("DPA: manjkajo podatki šole (nastavitve → DPA).")
    if not provider_complete(provider):
        raise ValueError("DPA: manjkajo podatki ponudnika (globalne nastavitve e-računov).")

    now = datetime.utcnow()
    school_sig = now.strftime("%d. %m. %Y %H:%M")
    provider_sig = now.strftime("%d. %m. %Y %H:%M")

    pdf = build_dpa_pdf(school, sdata, provider, school_sig, provider_sig)
    sha256 = hashlib.sha256(pdf).hexdigest()

    agreement = get_agreement(db, school.id)
    if agreement is None:
        agreement = DpaAgreement(school_id=school.id)
        db.add(agreement)
    agreement.version = DPA_VERSION
    agreement.school_json = json.dumps(sdata, ensure_ascii=False)
    agreement.provider_json = json.dumps(provider, ensure_ascii=False)
    agreement.signed_by_user_id = user.id
    agreement.signed_at = now
    agreement.pdf = pdf
    agreement.sha256 = sha256
    db.commit()
    db.refresh(agreement)
    return agreement


def reset_dpa(db: Session, school_id: int) -> bool:
    agreement = get_agreement(db, school_id)
    if agreement is None:
        return False
    db.delete(agreement)
    db.commit()
    return True
