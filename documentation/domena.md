🌐 **Jezik / Language:** [🇸🇮 Slovenščina](domena.md) | [🇬🇧 English](en/domena.md)

---

> ⚠️ **Opomba:** IP naslovi, gesla, email naslovi in drugi občutljivi podatki v tej
> dokumentaciji so zamenjani z zgledi. Za dejanske vrednosti preverite Kubernetes
> Secrets ali kontaktirajte administratorja.

---

# Domena – zamenjava iz `.local` na `ostc.si`

Trenutna domena: **`ostc-app.org`** (Cloudflare proxied)

---

## 📋 Trenutne DNS nastavitve

| Tip | Ime | Vrednost | Proxy | Namen |
|---|---|---|---|---|
| A | `ostc-app.org` | `192.168.1.2` | ✅ Proxied (oranžni oblak) | Aplikacija |

Cloudflare proxy pomeni:
- Javni DNS resolve-a na Cloudflare IP-je
- Cloudflare posreduje promet na `192.168.1.2:8080` (nginx na k3s-2, Flexible SSL)
- Cloudflare skrbi za SSL (Flexible — HTTPS do uporabnika, HTTP do k3s-2)
- `server: cloudflare` v HTTP headerjih

---

## 🔄 Prometni tok

```
🌐 Uporabnik → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → 192.168.1.2:8080 (k3s-2 nginx)
      → nginx proxy_pass http://192.168.1.10:8002
        → Service LoadBalancer (MetalLB)
          → sola-app pod (k3s-1 ali k3s-2)

Alternativna pot (notranje omrežje):
http://192.168.1.1:8080 → nginx na k3s-1 → proxy_pass 192.168.1.10:8002
http://192.168.1.2:8080 → nginx na k3s-2 → proxy_pass 192.168.1.10:8002
http://192.168.1.10:8002 → direkt na LoadBalancer
```

---

## 📜 Zgodovina sprememb domene

| Obdobje | Domena | Opis |
|---|---|---|
| Maj 2026 | `sola-app.local` | Začetna lokalna domena (mDNS) |
| Maj 2026 | `ostc.si` | Planirana zamenjava (ni bila implementirana) |
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
2. Dodaj A zapis: `@` → `192.168.1.10` (Proxied)
3. Počakaj, da se DNS propagira

### 2. Posodobi BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

### 3. Posodobi nginx (če je potrebno)

Na k3s-2:
```bash
sudo sed -i 's/ostc-app.org/nova-domena.si/' /etc/nginx/sites-available/default
sudo systemctl restart nginx
```

---

## 📌 Opombe

- **LoadBalancer IP** `192.168.1.10` je fiksen — ne spreminja se ob restartu
- **Nginx** na k3s-2 posreduje na MetalLB IP, ne direktno na pod-e
- **Cloudflare SSL** je "Full" — promet med Cloudflare in nginxom je HTTP (ne šifriran), vendar samo znotraj šolskega omrežja
- Če bi želeli **end-to-end HTTPS**, bi potrebovali certbot/letsencrypt na k3s-2
