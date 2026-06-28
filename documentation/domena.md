🌐 **Jezik / Language:** [🇸🇮 Slovenščina](domena.md) | [🇬🇧 English](en/domena.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# Domena — kako nas najde internet?

Trenutna domena: **`ostc-app.org`** (Cloudflare proxied — oranžni oblak prižgan 🟠)

---

## 📋 Kaj sploh je DNS? (ELI5)

> DNS je **telefonski imenik interneta**. Ko vtipkaš `ostc-app.org`, DNS pove brskalniku
> na kateri IP naj gre. Namesto da bi si zapomnil `{{LB_IP}}` (kar je grda številka),
> si zapomniš `ostc-app.org`. To je vse.

### Trenutne DNS nastavitve

| Tip | Ime | Vrednost | Proxy | Namen |
|-----|-----|----------|-------|-------|
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak 🟠) | Aplikacija — uporabniki pridejo sem |

---

## ☁️ Cloudflare proxy — kaj to pomeni? (ELI5)

> Cloudflare stoji pred aplikacijo kot **varnostnik**. Uporabnik vidi Cloudflare,
> ne vidi direktno strežnika. Cloudflare filtrira napade, skrbi za SSL certifikat
> in pospešuje nalaganje. Če te zanima, kdo je tvoj strežnik — ne moreš vedeti.
> Vidiš samo varnostnika.

**Oranžni oblak (Proxied) 🟠** — Cloudflare aktivno posreduje promet. Uporabnik
pokliče `ostc-app.org`, Cloudflare pogleda, ali je zahteva varna, in jo pošlje
naprej na `{{LB_IP}}`. Vse gre skozi Cloudflare.

**Siv oblak (DNS only) ⚪** — Cloudflare samo pove "hej, IP je `{{LB_IP}}`",
promet pa gre direktno od uporabnika do tvojega strežnika. Cloudflare ne vidi ničesar,
ne ščiti ničesar. Pri nas imamo oranžnega.

Cloudflare proxy v praksi pomeni:
- Javni DNS resolve-a na Cloudflare IP-je (ne na naš `{{LB_IP}}`)
- Cloudflare posreduje promet na `{{LB_IP}}` (LoadBalancer, port 80, Flexible SSL)
- Cloudflare skrbi za SSL
- V HTTP headerjih se pojavi `server: cloudflare`

---

## 🔐 Flexible SSL — polovična šifra (ELI5)

> Flexible SSL je kot **polovična šifra**. Med uporabnikom in Cloudflarom je HTTPS
> (zaklenjeno 🔒). Med Cloudflarom in našim strežnikom pa HTTP (odklenjeno 🔓).
> V šolskem omrežju je to OK, ker je promet znotraj zaupanja vrednega omrežja.
>
> Če bi aplikacija tekla na javnem WiFi-ju v kavarni, bi to bil problem.
> Ampak promet med Cloudflarom in `{{LB_IP}}` nikoli ne zapusti šolskega omrežja.
> Za šolo je to čisto dovolj dobro.

---

## 🔄 Prometni tok — kdo komu kaj pošilja

> 📊 **Diagram:** [`diagrams/domena-promet.drawio`](diagrams/domena-promet.drawio) — odpri v https://app.diagrams.net/

---

## ⚙️ BASE_URL — pove aplikaciji kakšen je njen polni spletni naslov (ELI5)

> BASE_URL pove aplikaciji kakšen je njen **polni spletni naslov**. To potrebuje
> za pošiljanje emailov (ko aplikacija reče "klikni na to povezavo", mora vedeti
> svoj naslov) in za preusmeritve (ko te pošlje iz ene strani na drugo).
>
> Če bi BASE_URL manjkal ali bil napačen, bi aplikacija pošiljala email povezave
> kot `http://localhost:3000/...» namesto `https://ostc-app.org/...» — in to ne
> deluje.

Konfiguracija v ConfigMap (`sola-config`, namespace `sola-app`):

```yaml
BASE_URL: "https://ostc-app.org"
```

---

## 📜 Zgodovina sprememb domene

| Obdobje       | Domena           | Opis                              |
|---------------|------------------|-----------------------------------|
| Maj 2026      | sola-app.local   | Začetna lokalna domena (mDNS)     |
| Junij 2026    | ostc-app.org     | Trenutna produkcijska domena 🏆   |

---

## 🛠️ Spreminjanje domene (če bi kdaj bilo treba)

Če bi bilo treba domeno spremeniti v prihodnosti:

### 1. Cloudflare — dodaj novo domeno in A zapis

1. Odpri Cloudflare dashboard
2. Dodaj A zapis: `@` → `{{LB_IP}}` (Proxied — oranžni oblak, LoadBalancer)
3. Počakaj, da se DNS propagira (lahko traja od nekaj minut do 48 ur, ponavadi ~5 min)

### 2. Posodobi BASE_URL v Kubernetes

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 📖 Pogoste zmede (FAQ za nestrpne)

### ❓ Zakaj ne vidim svojega strežnika ko pingam `ostc-app.org`?

> Ker imamo **oranžni oblak (Proxied)**. Ping gre na Cloudflare edge, ne na tvoj
> strežnik. Cloudflare se ne pusta pingat — vrže timeout. To je **normalno**.
> Tvoj strežnik je še vedno živ in zdrav. Če bi želel videti pravi IP, bi moral
> dati DNS v **siv oblak (DNS only)** — ampak tega nočemo, ker potem izgubimo
> Cloudflare zaščito.
>
> Za preverjanje strežnika uporabi `curl -v http://{{LB_IP}}:{{LB_PORT}}`
> direktno, ne ping.

### ❓ Ali rabim svoj SSL certifikat?

> Ne. Cloudflare ga daje zastonj. Ker imamo **Flexible SSL**, Cloudflare ustavi
> HTTPS na svojem robu in gre naprej HTTP do tvojega strežnika. Tvoj strežnik
> ne rabi nobenega certifikata. Če bi želel **end-to-end HTTPS** (Full ali
> Full Strict), bi moral namestiti certifikat še na aplikacijo — trenutno ni
> potrebe.

### ❓ Kaj če spremenim LoadBalancer IP?

> Če spremeniš `{{LB_IP}}` (na primer MetalLB restart ali sprememba konfiguracije),
> moraš **posodobiti DNS A zapis** v Cloudflare dashboardu na nov IP. Dokler
> ne posodobiš, Cloudflare pošilja promet na star (neobstoječ) IP in aplikacija
> ne bo dostopna. Svetujem:
> 1. Najprej nastavi nov IP v Cloudflare
> 2. Počakaj minuto
> 3. Šele potem spremeni LoadBalancer

---

## 📌 Opombe za staro dušo (DevOps)

- **LoadBalancer IP** `{{LB_IP}}` je fiksen — ne spreminja se ob restartu (hvala MetalLB za to)
- **Cloudflare SSL** je "Flexible" — HTTPS med uporabnikom in Cloudflarom, HTTP med Cloudflarom in `{{LB_IP}}` (znotraj šolskega omrežja — v redu)
- **server: cloudflare** se pojavi v HTTP headerjih — to je dokaz da Cloudflare posreduje
- Če bi želeli **end-to-end HTTPS**, bi potrebovali certifikat na aplikaciji (trenutno ni potrebe — ne kompliciraj)
- DNS propagacija lahko traja. Če si ravno spremenil DNS in ne dela — počakaj. Ne paničari. Skoči na `dig ostc-app.org` po 5 minutah.
