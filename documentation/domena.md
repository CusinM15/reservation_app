🌐 **Jezik / Language:** [🇸🇮 Slovenščina](domena.md) | [🇬🇧 English](en/domena.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# Domena

Trenutna domena: **`ostc-app.org`** (Cloudflare proxied)

---

## 📋 Trenutne DNS nastavitve

| Tip | Ime | Vrednost | Proxy | Namen |
|---|---|---|---|---|
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak) | Aplikacija (prek LoadBalancerja) |
| A | `www` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak) | WWW preusmeritev |

Cloudflare proxy (oranžni oblak) pomeni:
- Javni DNS resolve-a na Cloudflare IP-je (uporabnik vidi Cloudflare edge)
- Cloudflare posreduje promet na `{{LB_IP}}` (port 80, Flexible SSL)
- Cloudflare skrbi za SSL (Flexible — HTTPS do uporabnika, HTTP do LoadBalancerja)
- LoadBalancer (MetalLB) prejme promet na port 80 in ga posreduje sola-app podom na port 8002
- Če en node crkne, MetalLB samodejno premakne `{{LB_IP}}` na zdravi node — **HA deluje brez ročnega posega**

---

## 🔄 Prometni tok

```
🌐 Uporabnik → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → {{LB_IP}}:80 (LoadBalancer, MetalLB)
      → sola-app Pod (k3s-1 ali k3s-2) :8002

|http://{{LB_IP}}:{{LB_PORT}} → direkt na LoadBalancer (samo interno)
```

---

## 📜 Zgodovina sprememb domene

| Obdobje | Domena | Opis |
|---|---|---|
| Maj 2026 | `sola-app.local` | Začetna lokalna domena (mDNS) |
| Maj 2026 | `ostc.si` | Stara produkcijska domena |
| Junij 2026 | `sola-app.ostc.si` | Začasni testni URL |
| **Junij 2026** | **`ostc-app.org`** | **Trenutna produkcijska domena** |

---

## ⚙️ Konfiguracija v aplikaciji

`BASE_URL` v ConfigMap (`sola-config`, namespace `sola-app`):

```yaml
BASE_URL: "https://ostc-app.org"
```

---

## 🛠️ Spreminjanje domene

Če bi bilo treba domeno spremeniti v prihodnosti:

### 1. Cloudflare

1. Odpri Cloudflare dashboard
2. Dodaj A zapis: `@` → `{{LB_IP}}` (Proxied, LoadBalancer MetalLB IP)
3. Počakaj, da se DNS propagira

### 2. Posodobi BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```



---

## 📌 Opombe

- **Cloudflare → LB IP** (`{{LB_IP}}`) — promet gre direkt na MetalLB. Vmesni reverse proxy ni več del arhitekture.
- **Cloudflare SSL** je "Flexible" — HTTPS med uporabnikom in Cloudflarom, HTTP med Cloudflarom in LoadBalancerjem (`{{LB_IP}}:80`)
- **LoadBalancer** (MetalLB) posluša na portu 80 in posreduje na sola-app container port 8002
- Če bi želeli **end-to-end HTTPS** (Cloudflare → origin), bi potrebovali certbot/letsencrypt in spremenili SSL na "Full"

---

## 🏥 High Availability (HA)

### Zakaj Cloudflare → LB IP?

| Scenarij | Rezultat |
|---|---|
| k3s-1 crkne | MetalLB premakne `{{LB_IP}}` na k3s-2, pod se preseli → ✅ **HA deluje** |
| k3s-2 crkne | MetalLB premakne `{{LB_IP}}` na k3s-1, pod se preseli → ✅ **HA deluje** |
| Oba noda crkneta | Aplikacija ni dosegljiva → ❌ (ni cross-cluster HA) |

**Cloudflare ne ve, kateri node je živ** — preprosto pošilja promet na `{{LB_IP}}`. MetalLB skrbi, da je ta IP vedno na živem nodu.


