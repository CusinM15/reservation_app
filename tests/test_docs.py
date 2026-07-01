#!/usr/bin/env python3
"""
Pre-build test za PDF generacijo dokumentacije.

Usage:
    cd /app
    python tests/test_docs.py

To run inside Docker build (as a pre-build check), add to Dockerfile:
    COPY tests/ tests/
    RUN python tests/test_docs.py
"""

import sys
import os
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
APP_DIR = TESTS_DIR.parent
DOCS_DIR = APP_DIR / "documentation"
sys.path.insert(0, str(APP_DIR))

print("=" * 60)
print("📄 PRE-BUILD TEST — Dokumentacija / PDF")
print("=" * 60)

errors = []

# ── 1. Preveri datoteke ──
docs_to_check = {
    "navodila-ucitelji (SI)": DOCS_DIR / "navodila-ucitelji.md",
    "navodila-ucitelji (EN)": DOCS_DIR / "en" / "navodila-ucitelji.md",
    "navodila-vodstvo": DOCS_DIR / "navodila-vodstvo.md",
}
for label, path in docs_to_check.items():
    if path.exists():
        size = path.stat().st_size
        print(f"  ✅ {label}: {size:,} B")
    else:
        errors.append(f"Manjka datoteka: {label} na {path}")
        print(f"  ❌ {label}: MANJKA!")

# ── 2. Preveri slike ──
slike_dir = DOCS_DIR / "slike"
if slike_dir.exists():
    slike = list(slike_dir.glob("*.png"))
    print(f"  ✅ Slike v dokumentaciji: {len(slike)} PNG-jev")
    for s in slike:
        if s.stat().st_size < 1000:
            errors.append(f"Slika je sumljivo majhna: {s.name} ({s.stat().st_size} B)")
            print(f"  ⚠️  {s.name}: samo {s.stat().st_size} B")
else:
    errors.append(f"Mapa slike/ ne obstaja na {slike_dir}")

# ── 3. Preizkusi weasyprint PDF generacijo ──
try:
    from weasyprint import HTML as WP_HTML
    print("  ✅ weasyprint import OK")
except ImportError:
    errors.append("weasyprint ni nameščen!")
    print("  ❌ weasyprint ni dosegljiv")

# ── 3a. Test generacije SI PDF ──
try:
    si_path = DOCS_DIR / "navodila-ucitelji.md"
    if si_path.exists():
        md = si_path.read_text(encoding="utf-8")
        md_clean = __import__("re").sub(r'^🌐.*?\n---\s*\n', '', md, count=1, flags=__import__("re").DOTALL)
        md_clean = __import__("re").sub(r'^---\s*\n.*?\n---\s*\n', '', md_clean, count=1, flags=__import__("re").DOTALL)
        import markdown
        body = markdown.markdown(md_clean, extensions=["fenced_code", "tables"])
        css = """
        @page { margin: 2cm; }
        body { font-family: 'DejaVu Sans', sans-serif; font-size: 10.5pt; line-height: 1.6; }
        h1 { font-size: 18pt; color: #1a1a2e; border-bottom: 2px solid #4a6cf7; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 4pt 8pt; }
        img { max-width: 100%; }
        """
        full = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>{css}</style></head><body>
        <h1>Navodila za učitelje</h1>
        {body}
        </body></html>
        """
        pdf = WP_HTML(string=full).write_pdf()
        size_kb = len(pdf) / 1024
        if size_kb > 1:
            print(f"  ✅ SI PDF: {size_kb:.1f} KB")
        else:
            errors.append(f"SI PDF premajhen: {size_kb:.1f} KB")
            print(f"  ❌ SI PDF: samo {size_kb:.1f} KB")
except Exception as e:
    errors.append(f"SI PDF generacija padla: {e}")
    print(f"  ❌ SI PDF napaka: {e}")

# ── 3b. Test generacije EN PDF ──
try:
    en_path = DOCS_DIR / "en" / "navodila-ucitelji.md"
    if en_path.exists():
        md = en_path.read_text(encoding="utf-8")
        md_clean = __import__("re").sub(r'^🌐.*?\n---\s*\n', '', md, count=1, flags=__import__("re").DOTALL)
        md_clean = __import__("re").sub(r'^---\s*\n.*?\n---\s*\n', '', md_clean, count=1, flags=__import__("re").DOTALL)
        import markdown
        body = markdown.markdown(md_clean, extensions=["fenced_code", "tables"])
        full = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>{css}</style></head><body>
        <h1>Teacher Instructions</h1>
        {body}
        </body></html>
        """
        pdf = WP_HTML(string=full).write_pdf()
        size_kb = len(pdf) / 1024
        if size_kb > 1:
            print(f"  ✅ EN PDF: {size_kb:.1f} KB")
        else:
            errors.append(f"EN PDF premajhen: {size_kb:.1f} KB")
            print(f"  ❌ EN PDF: samo {size_kb:.1f} KB")
except Exception as e:
    errors.append(f"EN PDF generacija padla: {e}")
    print(f"  ❌ EN PDF napaka: {e}")

# ── 3c. Test generacije VODSTVO PDF ──
try:
    v_path = DOCS_DIR / "navodila-vodstvo.md"
    if v_path.exists():
        md = v_path.read_text(encoding="utf-8")
        md_clean = __import__("re").sub(r'^🌐.*?\n---\s*\n', '', md, count=1, flags=__import__("re").DOTALL)
        import markdown
        body = markdown.markdown(md_clean, extensions=["fenced_code", "tables"])
        full = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>{css}</style></head><body>
        <h1>Navodila za vodstvo in admin</h1>
        {body}
        </body></html>
        """
        pdf = WP_HTML(string=full).write_pdf()
        size_kb = len(pdf) / 1024
        if size_kb > 1:
            print(f"  ✅ Vodstvo PDF: {size_kb:.1f} KB")
        else:
            errors.append(f"Vodstvo PDF premajhen: {size_kb:.1f} KB")
            print(f"  ❌ Vodstvo PDF: samo {size_kb:.1f} KB")
except Exception as e:
    errors.append(f"Vodstvo PDF generacija padla: {e}")
    print(f"  ❌ Vodstvo PDF napaka: {e}")

# ── 4. Preveri, da vsebina ni prazna ──
for label, path in docs_to_check.items():
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if len(text.strip()) < 50:
            errors.append(f"{label} je (skoraj) prazna!")
            print(f"  ❌ {label}: PRAZNA!")
        elif "slika" not in text.lower() and "image" not in text.lower():
            # Ni nujno, da ima slike, ampak opozorimo
            print(f"  ⚠️  {label}: nima referenc na slike")

# ── 5. Preveri angleški prevod ──
en_path = DOCS_DIR / "en" / "navodila-ucitelji.md"
if en_path.exists():
    en_text = en_path.read_text(encoding="utf-8")
    # Preveri, da ni ostankov slovenščine v angleški datoteki
    si_words = ["učitelji", "vodstvo", "prijava", "geslo", "šolski"]
    found_si = [w for w in si_words if w in en_text.lower()]
    if found_si:
        print(f"  ⚠️  Angleška datoteka vsebuje slovenske besede: {found_si}")
    # Preveri, da ima angleški jezikovni izbirnik
    if "English" in en_text and "Language" in en_text:
        print("  ✅ EN: jezikovni izbirnik prisoten")
    else:
        errors.append("Angleška datoteka nima jezikovnega izbirnika!")
        print("  ❌ EN: manjka jezikovni izbirnik")
    # Preveri slikovne poti
    if "../slike/" in en_text:
        print("  ✅ EN: slikovne poti pravilne (../slike/)")
    else:
        errors.append("Angleška datoteka nima pravilnih slikovnih poti!")
        print("  ❌ EN: slikovne poti niso ../slike/")

# ── Zaključek ──
print()
print("=" * 60)
if errors:
    print(f"❌  PRE-BUILD TEST: {len(errors)} napak(e)!")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅  PRE-BUILD TEST: VSE OK — 0 napak")
    sys.exit(0)
