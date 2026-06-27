🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../domena.md) | [🇬🇧 English](domena.md)

---

# Domain – change from `.local` to `ostc.si`

Current domain: **`ostc-app.org`** (Cloudflare proxied)

---

## 📋 Current DNS settings

| Type | Name | Value | Proxy | Purpose |
|---|---|---|---|---|
| A | `ostc-app.org` | `193.2.171.200` | ✅ Proxied (orange cloud) | Application |

Cloudflare proxy means:
- Public DNS resolves to Cloudflare IPs (`104.21.81.50`, `172.67.156.249`)
- Cloudflare forwards traffic to `193.2.171.200:8080` (nginx on k3s-2)
- Cloudflare handles SSL (Auto SSL/TLS — Full)
- `server: cloudflare` in HTTP headers

---

## 🔄 Traffic flow

```
🌐 User → https://ostc-app.org
  → Cloudflare DNS → 104.21.81.50 (Cloudflare edge)
    → Cloudflare proxy → 193.2.171.200:8080
      → nginx (k3s-2, port 8080)
        → proxy_pass http://193.2.171.200:8002
          → Service LoadBalancer (MetalLB)
            → sola-app pod (k3s-1 or k3s-2)
```

---

## 📜 Domain change history

| Period | Domain | Description |
|---|---|---|
| May 2026 | `ostonecufar.local` | Initial local domain (mDNS) |
| May 2026 | `ostc.si` | Planned change (not implemented) |
| June 2026 | `sola-app.ostc.si` | Temporary test URL |
| **June 2026** | **`ostc-app.org`** | **Current production domain** |

---

## ⚙️ Application configuration

`BASE_URL` in ConfigMap (`sola-config`, namespace `sola-app`):

```yaml
BASE_URL: "https://ostc-app.org"
```

---

## 🛠️ Changing the domain

If the domain needs to be changed in the future:

### 1. Cloudflare

1. Open Cloudflare dashboard
2. Add A record: `@` → `193.2.171.200` (Proxied)
3. Wait for DNS propagation

### 2. Update BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

### 3. Update nginx (if needed)

On k3s-2:
```bash
sudo sed -i 's/ostc-app.org/nova-domena.si/' /etc/nginx/sites-available/default
sudo systemctl restart nginx
```

---

## 📌 Notes

- **LoadBalancer IP** `193.2.171.200` is fixed — it does not change on restart
- **Nginx** on k3s-2 forwards to the MetalLB IP, not directly to pods
- **Cloudflare SSL** is "Full" — traffic between Cloudflare and nginx is HTTP (not encrypted), but only within the school network
- If you wanted **end-to-end HTTPS**, you would need certbot/letsencrypt on k3s-2
