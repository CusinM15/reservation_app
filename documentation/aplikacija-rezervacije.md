🌐 **Jezik / Language:** [🇸🇮 Slovenščina](aplikacija-rezervacije.md) | [🇬🇧 English](en/aplikacija-rezervacije.md)

---

# 📱 Aplikacija za rezervacije in napovedi ocenjevanja

## Namen

Aplikacija je razvita za OŠ Toneta Čufarja Jesenice. Glavni namen je, ker šola potrebuje mrežni diagram za napoved ocenjevanja. Poleg tega omogoča tudi rezervacijo prostorov (računalnica, ladja, tablice, gospodinjska učilnica).

Ker avtor ne planira ostati dolgo na šoli, je aplikacija narejena čim bolj enostavno — tudi za osebe, ki niso vešče računalnika.

**Strežnik:** Ubuntu Server na starih računalnikih (preslabih za Windows 11), kar jim daje novo uporabno vrednost.

---

## Tehnologije

| Sloj | Tehnologija |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Podatkovna baza | PostgreSQL (produkcija) / SQLite (development) |
| Frontend | Jinja2 template, HTML/CSS/JS |
| Avtentikacija | cookie-based session z bcrypt hashom |
| Email | SMTP prek Arnesa (mail.arnes.si) |
| Orkestracija | Kubernetes (k3s) |
| Storage | Longhorn (distribuiran blokovni storage) |
| LoadBalancer | MetalLB |

---

## Spremenljivke za celotno aplikacijo — .env

```bash
# App settings
APP_HOST=0.0.0.0
APP_PORT=port na katerem teče app

DATABASE_URL=postgresql url

# Email settings
MAIL_USERNAME=kratek ime maila
MAIL_PASSWORD=*** maila
MAIL_SERVER=mail.arnes.si
MAIL_PORT=587
MAIL_FROM=mail iz katerega aplikacija pošilja sporočila
BACKUP_EMAIL=mail ki dnevno dobi backup baze
STANJE_MAIL=mail ki dnevno dobi poročilo o stanju klastra

# App config
TABLICE_MAX=število vseh tablic
SCHEDULE={"številka ure":"časovni interval ure"}
RAZREDI=seznam razredov
PROSTORI=seznam prostorov

# Session timeout (teacher)
INACTIVITY_TIMEOUT_MINUTES=po koliko časa se učitelj izpiše ob nedejavnosti
# Session timeout (admin/vodstvo)
INACTIVITY_TIMEOUT_ADMIN_MINUTES=po koliko časa se vodstvo/admin izpiše
```

---

## Funkcionalnosti

### Rezervacije prostorov

- **Tablice** — 28 kosov, lahko si jih deli več učiteljev v isti uri
- **Računalnica** — ena rezervacija na termin
- **Ladja** (pomivalni čoln) — ena rezervacija na termin
- **Gospodinjska učilnica** — ena rezervacija na termin

### Ocenjevanja

Napovedovanje pisnih ocenjevanj z omejitvami:
- Max 3 ocenjevanja na teden
- Max 2 običajni (neponavljalni) na teden
- Prepoved 3 zaporednih dni
- Samodejno preverjanje pravil za 1.–7. razred

### Zasedeni datumi

Vodstvo/admin označi dneve kot zasedene (športni dan, ekskurzija...). Sistem:
- Samodejno izbriše obstoječa ocenjevanja v tem obdobju
- Pošlje email obvestila prizadetim učiteljem

### Admin panel

Upravljanje uporabnikov — dodajanje, urejanje, brisanje, deaktivacija.

---

## Vloge uporabnikov

| Funkcija | Učitelj | Vodstvo | Admin |
|---|---|---|---|
| Rezervacija prostorov | ✅ | ✅ | ✅ |
| Brisanje lastne rezervacije | ✅ | ✅ | ✅ |
| Brisanje tuje rezervacije | ❌ | ✅ | ✅ |
| Napoved ocenjevanja | ✅ | ✅ | ✅ |
| Upravljanje zasedenih datumov | ❌ | ✅ | ✅ |
| Admin panel (uporabniki) | ❌ | ❌ | ✅ |
