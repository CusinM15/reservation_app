"""Probe: ali imajo VSI emoji v dokumentaciji Twemoji PNG?"""
import re
import sys
from pathlib import Path

DOCS = Path(r"C:\Matej\GitHub\reservation_app\documentation")
EMOJI_DIR = DOCS / "slike" / "emojis"

pattern = re.compile(
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]"
    r"[\uFE0F\u200D\U0001F3FB-\U0001F3FF\u2600-\u27BF\U0001F000-\U0001FAFF]*"
)

existing = {p.stem: p for p in EMOJI_DIR.glob("*.png")}
print("PNG-jev v mapi:", len(existing))

missing = []
found = set()
for md in DOCS.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    for m in pattern.finditer(text):
        seq = m.group(0)
        found.add(seq)
        i, n = 0, len(seq)
        while i < n:
            ch = seq[i]
            if ch in "\uFE0F\u200D":
                i += 1
                continue
            matched = False
            for cut in range(n, i, -1):
                cp = "-".join(f"{ord(c):x}" for c in seq[i:cut])
                if f"{cp}.png" in existing:
                    matched = True
                    break
            if not matched:
                missing.append((str(md), seq, hex(ord(ch))))
            i += 1

print("Unikatnih emoji sekvenc v dokumentaciji:", len(found))
if missing:
    print("MANJKA", len(missing), "PNG-jev:")
    for f, seq, ch in sorted(set(missing)):
        print("  ", f, repr(seq), "->", ch)
    sys.exit(1)
else:
    print("VSI emoji imajo PNG!")
