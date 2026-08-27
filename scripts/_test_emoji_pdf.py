
import sys, re
sys.path.insert(0, r"C:\Matej\GitHub\reservation_app")
from app.emoji_pdf import replace_emojis, render_emoji_png, _EMOJI_RE

# All emoji from navodila-ucitelji.md
from pathlib import Path
text = Path(r"C:\Matej\GitHub\reservation_app\documentation\navodila-ucitelji.md").read_text(encoding="utf-8")

# Find all emoji sequences with the module's regex
seqs = sorted(set(_EMOJI_RE.findall(text)))
print(f"Unikatnih emoji sekvenc (po regexu): {len(seqs)}")
for s in seqs:
    png = render_emoji_png(s)
    ok = "✅ PNG" if png else "❌ None"
    print(f"  {s!r} -> {ok} ({len(png)}B)" if png else f"  {s!r} -> {ok}")

# Also check VS16 variants — maybe regex splits them wrong
print("\n=== Preveri, ali regex ujame ZWJ/VS16 pravilno ===")
for test in ["👩\u200d🏫", "⚠️", "⚠", "🖥️", "🗓️", "✏️", "🛡️", "✅", "💡", "🫶"]:
    found = _EMOJI_RE.findall(test)
    print(f"  {test!r} -> regex najde: {found!r}")
