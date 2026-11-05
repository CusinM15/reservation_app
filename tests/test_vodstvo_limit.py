# Omejitev članov vodstva: največ MAX_VODSTVO (4) na šolo.
# Velja za ročno dodajanje (POST /admin/users) in CSV uvoz.
from app.routers.auth import MAX_VODSTVO
from tests.conftest import login


def _dodaj_vodstvo(client, username, i):
    return client.post(
        "/auth/admin/users",
        data={
            "username": username,
            "email": f"{username}@test.si",
            "first_name": "V",
            "last_name": f"odstvo{i}",
            "password": "Test12345!",
            "role": "vodstvo",
        },
        follow_redirects=False,
    )


def test_vodstvo_omejen_na_4_ročno(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)

    for i in range(MAX_VODSTVO):
        r = _dodaj_vodstvo(client, f"vod{i}", i)
        assert r.status_code == 303 and "error" not in r.headers.get("location", ""), (
            i, r.headers.get("location"))

    r = _dodaj_vodstvo(client, "vod_pet", 5)
    assert r.status_code == 303
    assert "omejeno" in r.headers.get("location", ""), r.headers.get("location")


def test_vodstvo_limit_ne_velja_za_teacher_in_admin(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    # učiteljev in admin ni omejitev (šola ima že MAX_VODSTVO vodstvo uporabnikov)
    for i in range(MAX_VODSTVO):
        _dodaj_vodstvo(client, f"v{i}", i)
    for i in range(3):
        r = client.post("/auth/admin/users",
                        data={"username": f"u{i}", "email": f"u{i}@t.si",
                              "first_name": "U", "last_name": "Ucitelj",
                              "password": "Test12345!", "role": "teacher"},
                        follow_redirects=False)
        assert r.status_code == 303 and "error" not in r.headers.get("location", "")


def test_vodstvo_limit_csv_uvoz(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    rows = "\n".join(f"vod{i}@s.si,V,Ime{i},vodstvo" for i in range(MAX_VODSTVO + 2))
    r = client.post(
        "/auth/admin/users/import",
        files={"file": ("u.csv", rows.encode("utf-8-sig"), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == MAX_VODSTVO, data
    assert data["skipped"] == 2, data
    assert any("omejeno" in e for e in data["errors"]), data["errors"]
