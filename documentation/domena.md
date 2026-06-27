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
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (oranžni oblak) | Aplikacija |

Cloudflare proxy pomeni:
- Javni DNS resolve-a na Cloudflare IP-je
- Cloudflare posreduje promet na `{{LB_IP}}` (LoadBalancer, port 80, Flexible SSL)
- Cloudflare skrbi za SSL (Flexible — HTTPS do uporabnika, HTTP do `{{LB_IP}}` na port 80)
- `server: cloudflare` v HTTP headerjih

---

## 🔄 Prometni tok

```
🌐 Uporabnik → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → `{{LB_IP}}:80` (MetalLB LoadBalancer)
      → sola-app pod (k3s-1 ali k3s-2)

Alternativna pot (notranje omrežje):
http://{{LB_IP}}:{{LB_PORT}} → direkt na LoadBalancer → sola-app pod
```

---

## 📜 Zgodovina sprememb domene

Obdobje       Domena           Opis
Maj 2026      sola-app.local   Začetna lokalna domena (mDNS)
Junij 2026    ostc-app.org     Trenutna produkcijska domena

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
2. Dodaj A zapis: `@` → `{{LB_IP}}` (Proxied, LoadBalancer)
3. Počakaj, da se DNS propagira

### 2. Posodobi BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 📌 Opombe

- **LoadBalancer IP** `{{LB_IP}}` je fiksen — ne spreminja se ob restartu
- **Cloudflare SSL** je "Flexible" — HTTPS med uporabnikom in Cloudflarom, HTTP med Cloudflarom in `{{LB_IP}}` (znotraj šolskega omrežja)
- Če bi želeli **end-to-end HTTPS**, bi potrebovali certifikat na aplikaciji (trenutno ni potrebe)
