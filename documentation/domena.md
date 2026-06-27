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
| A | `{{DOMAIN}}` | `{{K3S_2_IP}}` | ✅ Proxied (oranžni oblak) | Aplikacija |

Cloudflare proxy pomeni:
- Javni DNS resolve-a na Cloudflare IP-je
- Cloudflare posreduje promet na `192.168.1.2` (k3s-2, port 80, Flexible SSL)
- Cloudflare skrbi za SSL (Flexible — HTTPS do uporabnika, HTTP do k3s-2 na port 80)
- `server: cloudflare` v HTTP headerjih

---

## 🔄 Prometni tok

```
🌐 Uporabnik → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → 192.168.1.2:80 (k3s-2)
      → Service LoadBalancer (MetalLB, 192.168.1.10:8002)
        → sola-app pod (k3s-1 ali k3s-2)

Alternativna pot (notranje omrežje):
http://192.168.1.10 → direkt na LoadBalancer
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
2. Dodaj A zapis: `@` → `192.168.1.2` (Proxied, k3s-2)
3. Počakaj, da se DNS propagira

### 2. Posodobi BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 📌 Opombe

- **LoadBalancer IP** `192.168.1.10` je fiksen — ne spreminja se ob restartu
- **Cloudflare SSL** je "Flexible" — HTTPS med uporabnikom in Cloudflarom, HTTP med Cloudflarom in k3s-2 (znotraj šolskega omrežja)
- Če bi želeli **end-to-end HTTPS**, bi potrebovali certbot/letsencrypt na k3s-2
