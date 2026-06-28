🌐 **Jezik / Language:** [🇸🇮 Slovenščina](domena.md) | [🇬🇧 English](en/domena.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# 🌍 Domena in DNS — Kako deluje in zakaj je to pomembno

Trenutna domena: **`ostc-app.org`** (Cloudflare proxied — več o tem spodaj)

---

## 🏠 Kaj sploh je domena? (razlaga za začetnike)

**Domena je kot naslov tvoje hiše.** Predstavljaj si, da ima tvoj strežnik (računalnik, ki gosti aplikacijo) dolgo, grdo številko — nekaj takega kot `192.168.1.42` ali še slabše, `10.0.0.5`. Te številke se nihče ne spomni. Zato si izmislimo lepo ime, kot je **`ostc-app.org`** — tako kot si zapomniš "Cankarjeva ulica 12" namesto GPS koordinat.

**DNS (Domain Name System) je telefonski imenik interneta.** Ko v brskalnik vpišeš `ostc-app.org`, gre tvoj računalnik vprašat DNS-strežnik: "Hej, katera IP-številka se skriva za tem imenom?" DNS mu odgovori: "To je `{{LB_IP}}`." Šele nato brskalnik dejansko vzpostavi povezavo.

---

## ☁️ Cloudflare proxy (oranžni oblak) — kaj to pomeni?

V Cloudflare DNS-nastavitvah imaš dva načina:

| Ikona | Pomen | Kaj se zgodi? |
|---|---|---|
| 🟠 **Oranžni oblak** (Proxied) | Cloudflare stoji pred tvojim strežnikom | Brskalnik vidi Cloudflare-jev IP, ne tvojega pravega |
| 🔵 **Sivi oblak** (DNS only) | Cloudflare samo pove IP, potem gre direkt do strežnika | Brskalnik vidi tvoj pravi strežnik |

**Oranžni oblak je kot varnostnik pred vhodom v šolo:** Vsi obiskovalci najprej govorijo z njim. On preveri, kdo so, filtrira sumljiveže in šele nato spusti naprej k tvojemu strežniku. Tako strežnika nihče ne napada direktno — najprej mora skozi Cloudflare-jev ščit (DDoS zaščita, WAF firewall, IP-filterji itd.).

---

## 🔐 Flexible SSL — "sendvič" model varnosti

Cloudflare ponuja več načinov SSL. Pri nas uporabljamo **Flexible**:

```
🌐 Uporabnik ──🔒 HTTPS ──→ ☁️ Cloudflare ──🔓 HTTP ──→ 🖥️ Strežnik ({{LB_IP}}:80)
```

To pomeni:

- ✅ **Brskalnik ↔ Cloudflare:** Promet je zaklenjen (šifriran, HTTPS). Nihče na poti ne more brati, kaj pošiljaš.
- ⚠️ **Cloudflare ↔ tvoj strežnik:** Promet je **odklenjen** (nešifriran, HTTP). Ampak to je v **šolskem omrežju** OK, ker so vsi računalniki znotraj istega varnega omrežja — ni "nevarnih ulic" med Cloudflarom in strežnikom.

**Če bi želeli popolno šifriranje (end-to-end HTTPS):** bi morali na aplikaciji namestiti SSL-certifikat. Trenutno to ni potrebno, ker je notranje omrežje zaupano.

---

## 📋 Trenutne DNS nastavitve

| Tip | Ime | Vrednost | Proxy | Namen |
|---|---|---|---|---|
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak) | Aplikacija |

### 🔍 Kaj je A zapis?

**A zapis (Address record)** je najosnovnejši DNS-zapis. Reče: "Ime `ostc-app.org` pripada IP-naslovu `{{LB_IP}}`." To je kot v imeniku napisati: "Cankarjeva 12 → Hiša številka 5 na zemljevidu."

Obstaja še več tipov DNS-zapisov — AAAA (za IPv6), CNAME (preusmeritev na drugo ime), MX (za e-pošto) — ampak za aplikacijo rabiš samo **A zapis** s proxyjem.

---

## 🔄 Prometni tok — kaj se zgodi, ko nekdo odpre brskalnik?

![DNS prometni tok](diagrams/domena-promet.png)

### Alternativna pot (znotraj šolskega omrežja — ne gre prek Cloudflara)

```
http://{{LB_IP}}:{{LB_PORT}}
     → direktno na MetalLB LoadBalancer
       → sola-app pod
```

**Kdaj to uporabiš?** Ko si v šoli in želiš dostopati direktno, mimo Cloudflara. Npr. za testiranje, ko Cloudflare menda ne deluje. Ampak pojdi raje čez domeno, ker Cloudflare skrbi tudi za varnost.

---

## 📜 Zgodovina sprememb domene — zakaj smo šli skozi to?

| Obdobje | Domena | Zakaj? |
|---|---|---|
| Maj 2026 | `sola-app.local` | Začetek razvoja — samo lokalno, mDNS, noben zunanji dostop. To je kot da bi sosedom rekel "moja hiša je tista rdeča" — deluje le, če si v isti vasi. |
| Junij 2026 | `sola-app.ostc.si` | Začasni testni URL — prvič smo šli v javnost. Ampak `ostc.si` je glavna šolska domena, zato je bilo `sola-app.ostc.si` poddomena. |
| **Junij 2026** | **`ostc-app.org`** | **Trenutna produkcijska domena.** Kupili smo svojo domeno, da je sistem samostojen in neodvisen od ostalih šolskih storitev. Če bi kdaj zamenjali šolo ali ISP, vzamemo domeno s seboj. |

> **Pomembna lekcija:** Svoja domena = svoboda. `sola-app.local` ne moreš dati nikomur zunaj šole. Poddomena (`sola-app.ostc.si`) je odvisna od druge domene. Lastna domena (`ostc-app.org`) je tvoja, trajna in prenosljiva.

---

## ⚙️ Konfiguracija v aplikaciji

V Kubernetes ConfigMap (`sola-config`, namespace `sola-app`) je nastavljena `BASE_URL`:

```yaml
BASE_URL: "https://ostc-app.org"
```

**Zakaj to potrebujemo?** Aplikacija uporablja `BASE_URL` za:
- Povezave v email sporočilih (npr. "Klikni na to povezavo za potrditev")
- Preusmeritve po prijavi/odjavi
- Generiranje QR kod in drugih sklicev
- CORS nastavitve (katerim domenam je dovoljeno klicati API)

**Pravilo:** `BASE_URL` se mora vedno ujemati s tvojo javno domeno. Če zamenjaš domeno in pozabiš posodobiti `BASE_URL`, bodo povezave v emailih kazale na staro, nedelujočo domeno.

---

## 🛠️ Spreminjanje domene (če bi bilo potrebno v prihodnosti)

### 1️⃣ Cloudflare (DNS nastavitve)

1. Odpri Cloudflare dashboard
2. Pojdi v DNS nastavitve izbrane domene
3. Dodaj **A zapis**: `@` → `{{LB_IP}}` (Proxied = oranžni oblak)
4. Počakaj, da se DNS propagira
5. Počakaj, da se DNS propagira — to lahko traja od 1 minute do 24 ur! Ne paničari, če ne deluje takoj.

> ### ⏱️ Kaj pomeni "DNS propagacija"?
> Ko spremeniš DNS, nov podatek ne pride takoj na vse računalnike na svetu. Vsak DNS-strežnik ima svoj "cache" (začasni spomin). Ko popraviš zapis, Cloudflare takoj ve za spremembo, ampak tvoj internetni ponudnik (npr. Telemach, A1, T-2) ima morda star podatek shranjen še nekaj ur. Zato vidiš staro stran še nekaj časa.

### 2️⃣ Posodobi BASE_URL v aplikaciji

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

**Prvi ukaz** spremeni nastavitev. **Drugi ukaz** ponovno zažene aplikacijo, da spremembo upošteva. Oba morata biti izvedena.

### 3️⃣ Preveri, da vse deluje (glej spodnje poglavje)

---

## ❌ Pogoste napake pri DNS (in kako jih odpraviti)

### Napaka #1: A zapis ni proxied (siv oblak namesto oranžnega)

**Simptom:** Domena ne dela, brskalnik javlja napako, ker skuša iti direkt na `{{LB_IP}}`, ki nima SSL-certifikata.

**Rešitev:** V Cloudflare dashboardu spremeni ikono iz sive v oranžno (klikni nanjo — preklopi se). Počakaj minuto in osveži brskalnik.

### Napaka #2: Napačen LB_PORT

**Simptom:** Cloudflare proxy dela, ampak aplikacija javlja `502 Bad Gateway` (Cloudflare ne more do strežnika).

**Rešitev:** Preveri, da MetalLB LoadBalancer res posluša na portu **80** (HTTP). Včasih se zgodi, da je port spremenjen ali da pod ni dosegljiv. Preveri z:

```bash
kubectl -n sola-app get svc
```

### Napaka #3: BASE_URL je še vedno stara domena

**Simptom:** Aplikacija dela, ampak povezave v emailih in QR kodah kažejo na staro domeno.

**Rešitev:** Posodobi `BASE_URL` v ConfigMap in restartaj deployment (glej zgoraj).

### Napaka #4: DNS se še ni propagiral

**Simptom:** Na tvojem računalniku ne dela, na sosedovem pa dela (ali obratno).

**Rešitev:** Počakaj. Propagacija lahko traja do 24 ur, ampak ponavadi je v 5–30 minutah že uredu. Lahko poskusiš očistiti DNS cache na svojem računalniku:

- **Windows:** `ipconfig /flushdns`
- **Linux:** `sudo systemd-resolve --flush-caches` ali `sudo resolvectl flush-caches`
- **macOS:** `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`

### Napaka #5: Napačen DNS-strežnik

**Simptom:** Tvoj računalnik uporablja star ali napačen DNS-strežnik, ki ne pozna nove domene.

**Rešitev:** Za testiranje lahko uporabiš Googlov DNS (`8.8.8.8`) ali Cloudflare DNS (`1.1.1.1`), ki imata vedno sveže podatke.

---

## ✅ Kako preveriti, da domena deluje

### 🔹 1. Preizkus v brskalniku (najlažje)

Odpri brskalnik in v naslovno vrstico vpiši:

```
https://ostc-app.org
```

**Če deluje:** Vidiš aplikacijo. V naslovni vrstici je **zelena ključavnica** (HTTPS). Vse OK.

**Če ne deluje:** Dobiš napako. Preberi, kaj piše — `ERR_NAME_NOT_RESOLVED` pomeni DNS problem, `502 Bad Gateway` pomeni Cloudflare ne more do strežnika, `SSL_ERROR` pomeni težave s certifikatom.

### 🔹 2. Ping test (preveri, ali je domena dosegljiva)

Odpri terminal (ukazno vrstico) in vpiši:

```bash
ping ostc-app.org
```

**Če deluje:** Vidiš odgovore s časom v milisekundah. IP-naslov, ki ga vidiš, bo **Cloudflare-jev IP** (ne `{{LB_IP}}`) — to je pravilno, ker je proxy vklopljen.

**Če ne deluje:** Dobiš `ping: cannot resolve ostc-app.org: Unknown host` — DNS ne najde domene.

### 🔹 3. Dig test (natančen pregled DNS-zapisov)

```bash
dig ostc-app.org
```

To ti pokaže celoten DNS-odgovor. Poišči vrstico:

```
ostc-app.org.   XX  IN  A  (nek Cloudflare IP)
```

Če vidiš Cloudflare-jev IP namesto `{{LB_IP}}` → proxy deluje!  
Če vidiš `{{LB_IP}}` → proxy je izklopljen (siv oblak). To popravi.

Če ne vidiš ničesar → A zapis ni nastavljen ali se še propagira.

### 🔹 4. Nslookup (preprosta alternativa dig-u)

```bash
nslookup ostc-app.org
```

Podobno kot `dig` — pokaže IP-naslov, na katerega kaže domena.

### 🔹 5. Preveri HTTP headerje (ali Cloudflare posreduje promet?)

```bash
curl -I https://ostc-app.org
```

V odgovoru poišči:

```
server: cloudflare
```

Če to vidiš, gre promet skozi Cloudflare proxy — vse deluje kot mora.

### 🔹 6. Hitri preizkus propagacije

Uporabi spletna orodja (odpri v brskalniku):

- **https://dnschecker.org** — vpiši `ostc-app.org` in izberi A zapis. Pokaže ti, ali DNS zapis vidi cel svet ali samo določeni strežniki.
- **https://www.whatsmydns.net** — isto, le drugačen vmesnik.

---

## 📌 Opombe in povzetek

| Lastnost | Vrednost |
|---|---|
| **LoadBalancer IP** | `{{LB_IP}}` — fiksen, ne spreminja se ob restartu |
| **LoadBalancer Port** | `{{LB_PORT}}` |
| **SSL način** | Flexible — HTTPS do uporabnika, HTTP do strežnika |
| **DNS proxy** | ✅ Vklopljen (oranžni oblak) |
| **BASE_URL** | `https://ostc-app.org` |

### Ključne stvari, ki si jih zapomni:

1. **Domena = naslov, DNS = imenik.** Brez enega ne moreš do drugega.
2. **Oranžni oblak = varnost.** Vedno imej proxy vklopljen, razen če imaš zelo dober razlog, da ga izklopiš.
3. **Flexible SSL je varen v šolskem omrežju.** Če bi aplikacijo gostili na internetu (AWS, DigitalOcean ipd.), bi morali dati certifikat direkt na aplikacijo. Ampak ker smo v šoli, je Flexible SSL čisto dovolj.
4. **Ob menjavi domene vedno posodobi oboje:** Cloudflare DNS + `BASE_URL` v aplikaciji. Če pozabiš eno od obojega, ne bo delovalo.
5. **Počakaj na propagacijo.** DNS spremembe niso takojšnje. Ne spreminjaj iste stvari 10x v eni uri — vsakič začne propagacijo znova.
6. **Preveri z dig/ping/brskalnikom**, preden rečeš "ne deluje". Pogosto je težava le v tem, da si na starem DNS cache-u.

---

*Dokumentacija za sistem ostc-app — OŠ Toneta Čufarja Jesenice*
*Zadnja posodobitev: Junij 2026*
