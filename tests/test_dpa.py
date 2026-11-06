# tests/test_dpa.py — DPA: podpis v aplikaciji (šola + ponudnik samodejno)
#
# Zahteva uporabnika 2026-11-06: šolski admin izpolni podatke (sekcija DPA v
# nastavitvah), klikne »Podpiši« → dokument se podpiše z OBEMA stranema:
# šola (admin) + ponudnik (samodejno, podatki iz ERACUN_IZDAJATELJ_*).
from app.app_settings import set_app_setting
from app.database import SessionLocal
from app.dpa import get_agreement, provider_complete, provider_data, reset_dpa, sign_dpa
from app.models import School
from app.tenancy import set_school_setting
from tests.conftest import TEST_PASSWORD, default_school_id, login


def _pripravi_dpa_podatke(db, sid):
    set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
    set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1, 1000 Ljubljana")
    set_app_setting(db, "ERACUN_IZDAJATELJ_DAVCMA", "12345678")
    set_app_setting(db, "ERACUN_IZDAJATELJ_MATICNA", "99999999")
    set_app_setting(db, "ERACUN_IZDAJATELJ_EMAIL", "reservation.app@proton.me")
    set_school_setting(db, sid, "DPA_NASLOV", "Šolska ulica 5")
    set_school_setting(db, sid, "DPA_DAVCNA", "87654321")
    set_school_setting(db, sid, "DPA_MATICNA", "11112222")
    set_school_setting(db, sid, "DPA_ZASTOPNIK", "Test Admin")
    set_school_setting(db, sid, "DPA_FUNKCIJA", "ravnateljica")
    db.commit()


def test_dpa_provider_data_iz_eracun_nastavitev(client):
    db = SessionLocal()
    try:
        set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
        set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1")
        db.commit()
        p = provider_data(db)
        assert p["naziv"] == "Test ponudnik s.p."
        assert p["davcna"] == ""
        assert provider_complete(p)
        assert provider_complete({"naziv": "", "naslov": ""}) is False
    finally:
        db.close()


def test_dpa_sign_ustvari_podpisan_pdf(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        school = db.query(School).filter(School.id == sid).first()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin")

        a = sign_dpa(db, school, admin)
        assert a.pdf and len(a.pdf) > 1000
        assert a.pdf[:4] == b"%PDF"
        assert len(a.sha256) == 64
        assert a.signed_by_user_id == admin.id
        assert get_agreement(db, sid) is not None

        # ponovni podpis nadomesti obstoječi
        a2 = sign_dpa(db, school, admin)
        assert a2.id == a.id
        assert get_agreement(db, sid).sha256 == a2.sha256

        assert reset_dpa(db, sid) is True
        assert get_agreement(db, sid) is None
        assert reset_dpa(db, sid) is False
    finally:
        db.close()


def test_dpa_sign_brez_podatkov_sole_napaka(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        school = db.query(School).filter(School.id == sid).first()
        set_app_setting(db, "ERACUN_IZDAJATELJ_NAZIV", "Test ponudnik s.p.")
        set_app_setting(db, "ERACUN_IZDAJATELJ_NASLOV", "Trg 1")
        db.commit()
        admin = make_user(role="admin")
        try:
            sign_dpa(db, school, admin)
            raise AssertionError("pričakovana ValueError napaka")
        except ValueError:
            pass
    finally:
        db.close()


def test_dpa_api_potok(client, make_user):
    db = SessionLocal()
    try:
        sid = default_school_id()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin")
        username = admin.username
    finally:
        db.close()

    login(client, username)
    r = client.post("/settings/dpa/sign")
    assert r.status_code == 200, r.text
    assert r.json().get("sha256")

    r2 = client.get("/settings/dpa/pdf")
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("application/pdf")
    assert r2.content[:4] == b"%PDF"

    r3 = client.post("/settings/dpa/reset")
    assert r3.status_code == 200
    assert r3.json().get("ok") is True

    r4 = client.get("/settings/dpa/pdf")
    assert r4.status_code == 404


def test_ucitelj_ne_more_prijave_pred_podpisom_dpa(client, make_user):
    """Učitelj se ne more prijaviti, dokler šola ne podpiše DPA."""
    db = SessionLocal()
    try:
        admin = make_user(role="admin")
        teacher = make_user(role="teacher")
    finally:
        db.close()

    # u citelj -> login zavrnjen z napako o DPA
    r = client.post("/auth/login", data={"username": teacher.username, "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert "DPA" in r.text or "obdelavi osebnih" in r.text

    # admin -> prijava gre naprej (ima dostop, da podpiše)
    r2 = client.post("/auth/login", data={"username": admin.username, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)


def test_ucitelj_se_prijavi_po_podpisu_dpa(client, make_user):
    """Po podpisu DPA se učitelj normalno prijavi."""
    from app.dpa import sign_dpa
    from app.models import School
    db = SessionLocal()
    try:
        sid = default_school_id()
        school = db.query(School).filter(School.id == sid).first()
        _pripravi_dpa_podatke(db, sid)
        admin = make_user(role="admin")
        teacher = make_user(role="teacher")
        sign_dpa(db, school, admin)
    finally:
        db.close()

    # u citelj se zdaj prijavi (preusmeritev na aplikacijo)
    r2 = client.post("/auth/login", data={"username": teacher.username, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)


def test_vodstvo_dostop_zaslu_podpisom_dpa(client, make_user):
    """Vodstvo ima dostop tudi pred podpisom DPA (da šolo pripravi)."""
    from app.models import RoleEnum
    db = SessionLocal()
    try:
        vodstvo = make_user(role="vodstvo")
    finally:
        db.close()
    r2 = client.post("/auth/login", data={"username": vodstvo.username, "password": TEST_PASSWORD},
                     follow_redirects=False)
    assert r2.status_code in (302, 303)
