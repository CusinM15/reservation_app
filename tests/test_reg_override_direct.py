from app.database import SessionLocal
from app.models import AppSetting, UIString as _UIStr
from app import template_override as tov


def test_direkten_render_registracija_overridea(client):
    MARK = "OVERRIDE_REG_DIRECT_MMMM"
    db = SessionLocal()
    try:
        db.add(AppSetting(key="TEMPLATE_OVERRIDE:registracija.html",
                          value="<html><body>%s</body></html>" % MARK))
        db.commit()
        # ali reg_intro obstaja v ui_strings?
        has = db.query(_UIStr).filter(_UIStr.key == "reg_intro").first()
        print("  reg_intro v ui_strings:", (has.key if has else None))
    finally:
        db.close()
    tov.invalidate("registracija.html")

    from app.templating import make_templates
    tpl = make_templates()
    src, name, upto = tpl.env.loader.get_source(tpl.env, "registracija.html")
    print("  loader vrača filename:", name)
    print("  loader vrača override?", MARK in src, "| vrste uptodate:", type(upto).__name__)
    assert MARK in src, "OverrideLoader ni vrnil override-a za registracija.html!"