
import sys
sys.path.insert(0, r"C:\Matej\GitHub\reservation_app")
from app.emoji_pdf import replace_emojis, render_emoji_png

try:
    png = render_emoji_png("✅")
    print("render ✅:", "PNG bajtov" if png else "None")
except Exception as e:
    print("render ✅ exception:", type(e).__name__, str(e)[:120])

out = replace_emojis("<p>✅ Opozorilo in 👩🏫 učitelj</p>")
print("replace_emojis:", out[:200])

import re
from app.emoji_pdf import _EMOJI_RE
print("regex najde:", _EMOJI_RE.findall("<p>✅ Opozorilo in 👩🏫 učitelj ⚠️</p>"))
