# ─────────────────────────────────────────────────────────────────────────
# app/templating.py — skupna Jinja2 predloga z večjezičnim napisom t()
#
# Zakaj? Vsak ruter (in main) ustvari svoj Jinja2Templates z lastnim
# okoljem. Da je funkcija {{ t('kljuc', 'privzeto') }} na voljo v VSEH
# predlogah, predloge ustvarimo prek te tovarne, ki doda global »t«.
# ─────────────────────────────────────────────────────────────────────────

from fastapi.templating import Jinja2Templates

from app.i18n import current_lang, t as _ui_t


def make_templates(directory: str = "app/templates") -> Jinja2Templates:
    """Ustvari Jinja2Templates z globalom t() (napis iz baze v izbranem jeziku)."""
    tpl = Jinja2Templates(directory=directory)
    tpl.env.globals["t"] = _ui_t          # {{ t('kljuc', 'privzeto') }}
    tpl.env.globals["ui_lang"] = current_lang  # {{ ui_lang() }} → 'sl' ali 'en'
    return tpl
