     1|🌐 **Jezik / Language:** [🇸🇮 Slovenščina](domena.md) | [🇬🇧 English](en/domena.md)
     2|
     3|---
     4|
     5|> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
     6|> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
     7|> Secrets ali kontaktirajte administratorja.
     8|
     9|---
    10|
    11|# 🌍 Domena in DNS — Kako deluje in zakaj je to pomembno
    12|
    13|Trenutna domena: **`ostc-app.org`** (Cloudflare proxied — več o tem spodaj)
    14|
    15|---
    16|
    17|## 🏠 Kaj sploh je domena? (razlaga za začetnike)
    18|
    19|**Domena je kot naslov tvoje hiše.** Predstavljaj si, da ima tvoj strežnik (računalnik, ki gosti aplikacijo) dolgo, grdo številko — nekaj takega kot `192.168.1.42` ali še slabše, `10.0.0.5`. Te številke se nihče ne spomni. Zato si izmislimo lepo ime, kot je **`ostc-app.org`** — tako kot si zapomniš "Cankarjeva ulica 12" namesto GPS koordinat.
    20|
    21|**DNS (Domain Name System) je telefonski imenik interneta.** Ko v brskalnik vpišeš `ostc-app.org`, gre tvoj računalnik vprašat DNS-strežnik: "Hej, katera IP-številka se skriva za tem imenom?" DNS mu odgovori: "To je `{{LB_IP}}`." Šele nato brskalnik dejansko vzpostavi povezavo.
    22|
    23|---
    24|
    25|## ☁️ Cloudflare proxy (oranžni oblak) — kaj to pomeni?
    26|
    27|V Cloudflare DNS-nastavitvah imaš dva načina:
    28|
    29|| Ikona | Pomen | Kaj se zgodi? |
    30||---|---|---|
    31|| 🟠 **Oranžni oblak** (Proxied) | Cloudflare stoji pred tvojim strežnikom | Brskalnik vidi Cloudflare-jev IP, ne tvojega pravega |
    32|| 🔵 **Sivi oblak** (DNS only) | Cloudflare samo pove IP, potem gre direkt do strežnika | Brskalnik vidi tvoj pravi strežnik |
    33|
    34|**Oranžni oblak je kot varnostnik pred vhodom v šolo:** Vsi obiskovalci najprej govorijo z njim. On preveri, kdo so, filtrira sumljiveže in šele nato spusti naprej k tvojemu strežniku. Tako strežnika nihče ne napada direktno — najprej mora skozi Cloudflare-jev ščit (DDoS zaščita, WAF firewall, IP-filterji itd.).
    35|
    36|---
    37|
    38|## 🔐 Flexible SSL — "sendvič" model varnosti
    39|
    40|Cloudflare ponuja več načinov SSL. Pri nas uporabljamo **Flexible**:
    41|
    42|```
    43|🌐 Uporabnik ──🔒 HTTPS ──→ ☁️ Cloudflare ──🔓 HTTP ──→ 🖥️ Strežnik ({{LB_IP}}:80)
    44|```
    45|
    46|To pomeni:
    47|
    48|- ✅ **Brskalnik ↔ Cloudflare:** Promet je zaklenjen (šifriran, HTTPS). Nihče na poti ne more brati, kaj pošiljaš.
    49|- ⚠️ **Cloudflare ↔ tvoj strežnik:** Promet je **odklenjen** (nešifriran, HTTP). Ampak to je v **šolskem omrežju** OK, ker so vsi računalniki znotraj istega varnega omrežja — ni "nevarnih ulic" med Cloudflarom in strežnikom.
    50|
    51|**Če bi želeli popolno šifriranje (end-to-end HTTPS):** bi morali na aplikaciji namestiti SSL-certifikat. Trenutno to ni potrebno, ker je notranje omrežje zaupano.
    52|
    53|---
    54|
    55|## 📋 Trenutne DNS nastavitve
    56|
    57|| Tip | Ime | Vrednost | Proxy | Namen |
    58||---|---|---|---|---|
    59|| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak) | Aplikacija |
    60|
    61|### 🔍 Kaj je A zapis?
    62|
    63|**A zapis (Address record)** je najosnovnejši DNS-zapis. Reče: "Ime `ostc-app.org` pripada IP-naslovu `{{LB_IP}}`." To je kot v imeniku napisati: "Cankarjeva 12 → Hiša številka 5 na zemljevidu."
    64|
    65|Obstaja še več tipov DNS-zapisov — AAAA (za IPv6), CNAME (preusmeritev na drugo ime), MX (za e-pošto) — ampak za aplikacijo rabiš samo **A zapis** s proxyjem.
    66|
    67|---
    68|
    69|## 🔄 Prometni tok — kaj se zgodi, ko nekdo odpre brskalnik?
    70|
    71|> 📐 **Diagram:** odpri `diagrams/domena-promet.drawio` v [app.diagrams.net](https://app.diagrams.net) (File → Open)
    72|
    73|
   109|
   110|### Alternativna pot (znotraj šolskega omrežja — ne gre prek Cloudflara)
   111|
   112|```
   113|http://{{LB_IP}}:{{LB_PORT}}
   114|     → direktno na MetalLB LoadBalancer
   115|       → sola-app pod
   116|```
   117|
   118|**Kdaj to uporabiš?** Ko si v šoli in želiš dostopati direktno, mimo Cloudflara. Npr. za testiranje, ko Cloudflare menda ne deluje. Ampak pojdi raje čez domeno, ker Cloudflare skrbi tudi za varnost.
   119|
   120|---
   121|
   122|## 📜 Zgodovina sprememb domene — zakaj smo šli skozi to?
   123|
   124|| Obdobje | Domena | Zakaj? |
   125||---|---|---|
   126|| Maj 2026 | `sola-app.local` | Začetek razvoja — samo lokalno, mDNS, noben zunanji dostop. To je kot da bi sosedom rekel "moja hiša je tista rdeča" — deluje le, če si v isti vasi. |
   127|| Junij 2026 | `sola-app.ostc.si` | Začasni testni URL — prvič smo šli v javnost. Ampak `ostc.si` je glavna šolska domena, zato je bilo `sola-app.ostc.si` poddomena. |
   128|| **Junij 2026** | **`ostc-app.org`** | **Trenutna produkcijska domena.** Kupili smo svojo domeno, da je sistem samostojen in neodvisen od ostalih šolskih storitev. Če bi kdaj zamenjali šolo ali ISP, vzamemo domeno s seboj. |
   129|
   130|> **Pomembna lekcija:** Svoja domena = svoboda. `sola-app.local` ne moreš dati nikomur zunaj šole. Poddomena (`sola-app.ostc.si`) je odvisna od druge domene. Lastna domena (`ostc-app.org`) je tvoja, trajna in prenosljiva.
   131|
   132|---
   133|
   134|## ⚙️ Konfiguracija v aplikaciji
   135|
   136|V Kubernetes ConfigMap (`sola-config`, namespace `sola-app`) je nastavljena `BASE_URL`:
   137|
   138|```yaml
   139|BASE_URL: "https://ostc-app.org"
   140|```
   141|
   142|**Zakaj to potrebujemo?** Aplikacija uporablja `BASE_URL` za:
   143|- Povezave v email sporočilih (npr. "Klikni na to povezavo za potrditev")
   144|- Preusmeritve po prijavi/odjavi
   145|- Generiranje QR kod in drugih sklicev
   146|- CORS nastavitve (katerim domenam je dovoljeno klicati API)
   147|
   148|**Pravilo:** `BASE_URL` se mora vedno ujemati s tvojo javno domeno. Če zamenjaš domeno in pozabiš posodobiti `BASE_URL`, bodo povezave v emailih kazale na staro, nedelujočo domeno.
   149|
   150|---
   151|
   152|## 🛠️ Spreminjanje domene (če bi bilo potrebno v prihodnosti)
   153|
   154|### 1️⃣ Cloudflare (DNS nastavitve)
   155|
   156|1. Odpri Cloudflare dashboard
   157|2. Pojdi v DNS nastavitve izbrane domene
   158|3. Dodaj **A zapis**: `@` → `{{LB_IP}}` (Proxied = oranžni oblak)
   159|4. Počakaj, da se DNS propagira
   160|5. Počakaj, da se DNS propagira — to lahko traja od 1 minute do 24 ur! Ne paničari, če ne deluje takoj.
   161|
   162|> ### ⏱️ Kaj pomeni "DNS propagacija"?
   163|> Ko spremeniš DNS, nov podatek ne pride takoj na vse računalnike na svetu. Vsak DNS-strežnik ima svoj "cache" (začasni spomin). Ko popraviš zapis, Cloudflare takoj ve za spremembo, ampak tvoj internetni ponudnik (npr. Telemach, A1, T-2) ima morda star podatek shranjen še nekaj ur. Zato vidiš staro stran še nekaj časa.
   164|
   165|### 2️⃣ Posodobi BASE_URL v aplikaciji
   166|
   167|```bash
   168|kubectl -n sola-app patch configmap sola-config --type merge \
   169|  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
   170|kubectl -n sola-app rollout restart deployment/sola-app
   171|```
   172|
   173|**Prvi ukaz** spremeni nastavitev. **Drugi ukaz** ponovno zažene aplikacijo, da spremembo upošteva. Oba morata biti izvedena.
   174|
   175|### 3️⃣ Preveri, da vse deluje (glej spodnje poglavje)
   176|
   177|---
   178|
   179|## ❌ Pogoste napake pri DNS (in kako jih odpraviti)
   180|
   181|### Napaka #1: A zapis ni proxied (siv oblak namesto oranžnega)
   182|
   183|**Simptom:** Domena ne dela, brskalnik javlja napako, ker skuša iti direkt na `{{LB_IP}}`, ki nima SSL-certifikata.
   184|
   185|**Rešitev:** V Cloudflare dashboardu spremeni ikono iz sive v oranžno (klikni nanjo — preklopi se). Počakaj minuto in osveži brskalnik.
   186|
   187|### Napaka #2: Napačen LB_PORT
   188|
   189|**Simptom:** Cloudflare proxy dela, ampak aplikacija javlja `502 Bad Gateway` (Cloudflare ne more do strežnika).
   190|
   191|**Rešitev:** Preveri, da MetalLB LoadBalancer res posluša na portu **80** (HTTP). Včasih se zgodi, da je port spremenjen ali da pod ni dosegljiv. Preveri z:
   192|
   193|```bash
   194|kubectl -n sola-app get svc
   195|```
   196|
   197|### Napaka #3: BASE_URL je še vedno stara domena
   198|
   199|**Simptom:** Aplikacija dela, ampak povezave v emailih in QR kodah kažejo na staro domeno.
   200|
   201|**Rešitev:** Posodobi `BASE_URL` v ConfigMap in restartaj deployment (glej zgoraj).
   202|
   203|### Napaka #4: DNS se še ni propagiral
   204|
   205|**Simptom:** Na tvojem računalniku ne dela, na sosedovem pa dela (ali obratno).
   206|
   207|**Rešitev:** Počakaj. Propagacija lahko traja do 24 ur, ampak ponavadi je v 5–30 minutah že uredu. Lahko poskusiš očistiti DNS cache na svojem računalniku:
   208|
   209|- **Windows:** `ipconfig /flushdns`
   210|- **Linux:** `sudo systemd-resolve --flush-caches` ali `sudo resolvectl flush-caches`
   211|- **macOS:** `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`
   212|
   213|### Napaka #5: Napačen DNS-strežnik
   214|
   215|**Simptom:** Tvoj računalnik uporablja star ali napačen DNS-strežnik, ki ne pozna nove domene.
   216|
   217|**Rešitev:** Za testiranje lahko uporabiš Googlov DNS (`8.8.8.8`) ali Cloudflare DNS (`1.1.1.1`), ki imata vedno sveže podatke.
   218|
   219|---
   220|
   221|## ✅ Kako preveriti, da domena deluje
   222|
   223|### 🔹 1. Preizkus v brskalniku (najlažje)
   224|
   225|Odpri brskalnik in v naslovno vrstico vpiši:
   226|
   227|```
   228|https://ostc-app.org
   229|```
   230|
   231|**Če deluje:** Vidiš aplikacijo. V naslovni vrstici je **zelena ključavnica** (HTTPS). Vse OK.
   232|
   233|**Če ne deluje:** Dobiš napako. Preberi, kaj piše — `ERR_NAME_NOT_RESOLVED` pomeni DNS problem, `502 Bad Gateway` pomeni Cloudflare ne more do strežnika, `SSL_ERROR` pomeni težave s certifikatom.
   234|
   235|### 🔹 2. Ping test (preveri, ali je domena dosegljiva)
   236|
   237|Odpri terminal (ukazno vrstico) in vpiši:
   238|
   239|```bash
   240|ping ostc-app.org
   241|```
   242|
   243|**Če deluje:** Vidiš odgovore s časom v milisekundah. IP-naslov, ki ga vidiš, bo **Cloudflare-jev IP** (ne `{{LB_IP}}`) — to je pravilno, ker je proxy vklopljen.
   244|
   245|**Če ne deluje:** Dobiš `ping: cannot resolve ostc-app.org: Unknown host` — DNS ne najde domene.
   246|
   247|### 🔹 3. Dig test (natančen pregled DNS-zapisov)
   248|
   249|```bash
   250|dig ostc-app.org
   251|```
   252|
   253|To ti pokaže celoten DNS-odgovor. Poišči vrstico:
   254|
   255|```
   256|ostc-app.org.   XX  IN  A  (nek Cloudflare IP)
   257|```
   258|
   259|Če vidiš Cloudflare-jev IP namesto `{{LB_IP}}` → proxy deluje!  
   260|Če vidiš `{{LB_IP}}` → proxy je izklopljen (siv oblak). To popravi.
   261|
   262|Če ne vidiš ničesar → A zapis ni nastavljen ali se še propagira.
   263|
   264|### 🔹 4. Nslookup (preprosta alternativa dig-u)
   265|
   266|```bash
   267|nslookup ostc-app.org
   268|```
   269|
   270|Podobno kot `dig` — pokaže IP-naslov, na katerega kaže domena.
   271|
   272|### 🔹 5. Preveri HTTP headerje (ali Cloudflare posreduje promet?)
   273|
   274|```bash
   275|curl -I https://ostc-app.org
   276|```
   277|
   278|V odgovoru poišči:
   279|
   280|```
   281|server: cloudflare
   282|```
   283|
   284|Če to vidiš, gre promet skozi Cloudflare proxy — vse deluje kot mora.
   285|
   286|### 🔹 6. Hitri preizkus propagacije
   287|
   288|Uporabi spletna orodja (odpri v brskalniku):
   289|
   290|- **https://dnschecker.org** — vpiši `ostc-app.org` in izberi A zapis. Pokaže ti, ali DNS zapis vidi cel svet ali samo določeni strežniki.
   291|- **https://www.whatsmydns.net** — isto, le drugačen vmesnik.
   292|
   293|---
   294|
   295|## 📌 Opombe in povzetek
   296|
   297|| Lastnost | Vrednost |
   298||---|---|
   299|| **LoadBalancer IP** | `{{LB_IP}}` — fiksen, ne spreminja se ob restartu |
   300|| **LoadBalancer Port** | `{{LB_PORT}}` |
   301|| **SSL način** | Flexible — HTTPS do uporabnika, HTTP do strežnika |
   302|| **DNS proxy** | ✅ Vklopljen (oranžni oblak) |
   303|| **BASE_URL** | `https://ostc-app.org` |
   304|
   305|### Ključne stvari, ki si jih zapomni:
   306|
   307|1. **Domena = naslov, DNS = imenik.** Brez enega ne moreš do drugega.
   308|2. **Oranžni oblak = varnost.** Vedno imej proxy vklopljen, razen če imaš zelo dober razlog, da ga izklopiš.
   309|3. **Flexible SSL je varen v šolskem omrežju.** Če bi aplikacijo gostili na internetu (AWS, DigitalOcean ipd.), bi morali dati certifikat direkt na aplikacijo. Ampak ker smo v šoli, je Flexible SSL čisto dovolj.
   310|4. **Ob menjavi domene vedno posodobi oboje:** Cloudflare DNS + `BASE_URL` v aplikaciji. Če pozabiš eno od obojega, ne bo delovalo.
   311|5. **Počakaj na propagacijo.** DNS spremembe niso takojšnje. Ne spreminjaj iste stvari 10x v eni uri — vsakič začne propagacijo znova.
   312|6. **Preveri z dig/ping/brskalnikom**, preden rečeš "ne deluje". Pogosto je težava le v tem, da si na starem DNS cache-u.
   313|
   314|---
   315|
   316|*Dokumentacija za sistem ostc-app — OŠ Toneta Čufarja Jesenice*
   317|*Zadnja posodobitev: Junij 2026*
   318|