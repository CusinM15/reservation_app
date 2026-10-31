# tests/test_eracun.py — e-račun: izdaja, shranjevanje v invoices, podpis
#
# Pokriva POST /narocnina/e-racun: izda e-SLOG 2.0 račun za LETNO naročnino,
# ga pošlje na e-pošto šole (v testih SMTP ni nastavljen → pošiljanje ne uspe)
# in VSEENO shrani vrstico v tabelo `invoices`. Ločeno: si_sklic, XML vključno
# s podpisom, in POST /narocnina/izdajatelj (shranjevanje podatkov izdajatelja).
#
# NOTE: večina testov dela neodvisno od omrežja — edino /narocnina/e-racun
# poskuša poslati SMTP (pade, a račun se shrani s statusom "error"), kar je
# natanko želeno daljinsko vedenje v testnem okolju.
# ─────────────────────────────────────────────────────────────────────────
import pytest

from datetime import date

from app.app_settings import (
    KEY_ISSUER_NAME,
    KEY_ISSUER_ADDRESS,
    KEY_ISSUER_POST,
    KEY_ISSUER_TAX,
    KEY_ISSUER_IBAN,
    KEY_ISSUER_EMAIL,
    KEY_ISSUER_SIGN,
    KEY_PRICE,
    set_app_setting,
)
from app.database import SessionLocal
from app.eracun import build_invoice_xml, si_sklic
from app.models import Invoice
from tests.conftest import login, default_school_id

ISSUER = {
    KEY_ISSUER_NAME: "Podjetje s.p.",
    KEY_ISSUER_ADDRESS: "Cesta 1",
    KEY_ISSUER_POST: "4000 Kranj",
    KEY_ISSUER_TAX: "SI12345678",
    KEY_ISSUER_IBAN: "SI56 1234 0000 0000 000",
    KEY_ISSUER_EMAIL: "racuni@firma.si",
    KEY_ISSUER_SIGN: "Janez Podpisnik",
}


def _set_issuer(price: str = "150") -> None:
    """Zapiši izdajatelja (vklj. podpis) + ceno v app_settings."""
    db = SessionLocal()
    try:
        for key, value in ISSUER.items():
            set_app_setting(db, key, value)
        set_app_setting(db, KEY_PRICE, price)
        db.commit()
    finally:
        db.close()


def _invoice_rows(school_id: int):
    db = SessionLocal()
    try:
        return db.query(Invoice).filter(Invoice.school_id == school_id).all()
    finally:
        db.close()


def test_izdaj_e_racun_shrani_invoice(client, make_user):
    _set_issuer()
    admin = make_user(role="admin")
    login(client, admin.username)
    school_id = default_school_id()

    r = client.post(
        "/narocnina/e-racun",
        data={"school_id": str(school_id)},
        follow_redirects=False,
    )
    assert r.status_code == 303

    rows = _invoice_rows(school_id)
    assert len(rows) == 1
    inv = rows[0]
    assert inv.number.startswith(str(date.today().year))
    assert inv.amount_gross > 0
    # SMTP za mock ni nastavljen → pošiljanje ne uspe, a račun se vseeno shrani.
    assert inv.status == "error"
    assert inv.xml                      # e-SLOG XML je shranjen
    assert "SI56 1234" in inv.issuer    # izdajatelj iz globalnih nastavitev
    assert inv.buyer_email              # kupec = e-pošta šole
    assert inv.sklic                    # slovenska referenca (sklic)


def test_eracun_potrebuje_izdajatelja(client, make_user):
    # Ni izdajatelja → 303 redirect z error, brez invoice.
    admin = make_user(role="admin")
    login(client, admin.username)
    school_id = default_school_id()
    r = client.post(
        "/narocnina/e-racun",
        data={"school_id": str(school_id)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert len(_invoice_rows(school_id)) == 0


def test_izdajatelj_stran_zahteva_main_admin(client, make_user):
    # Šolski admin nima dostopa do /narocnina/izdajatelj.
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/narocnina/izdajatelj")
    assert r.status_code == 403


def test_si_sklic_valid_mod97():
    for n in (1, 12, 123, 999, 10023):
        s = si_sklic(n)
        # Sestavljeno iz številke + 2 kontrolni števki, predpona SI.
        digits = s[2:]
        assert digits[:-2] == str(n)
        # Preverbna števka: (osnova*100 + kontrolna) % 97 == 1
        base = str(n)
        check = int(digits[-2:])
        assert (n * 100 + check) % 97 == 1


def test_build_invoice_xml_vsebuje_podpis():
    inv = {
        "number": "2026-001", "issue_date": date(2026, 9, 1),
        "due_date": date(2026, 9, 16),
        "currency": "EUR", "sklic": "SI00188",
        "net": 100.0, "ddv": 22.0, "gross": 122.0,
        "unit_net": 100.0, "qty": 1,
        "item_name": "Letna naročnina", "item_desc": "opomba",
        "issuer": {"name": "Firma s.p.", "address": "Cesta 1", "post": "4000 Kranj",
                   "tax": "SI12345678", "iban": "SI56 1234 0000 0000 000",
                   "email": "r@f.si", "sign": "Janez Podpisnik"},
        "buyer": {"name": "Šola", "address": "", "post": "",
                  "tax": "", "email": "sola@sk.si"},
    }
    xml = build_invoice_xml(inv)
    assert "<cac:Signature>" in xml
    assert "Janez Podpisnik" in xml          # podpis v XML
    assert "<cbc:ID>2026-001</cbc:ID>" in xml
    assert "SI56 1234" in xml
    assert "<cbc:PayableAmount>122.00</cbc:PayableAmount>" in xml