🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../domena.md) | [🇬🇧 English](domena.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# Domain – change from `.local` to `ostc.si`

Current domain: **`ostc-app.org`** (Cloudflare proxied)

---

## 📋 Current DNS settings

| Type | Name | Value | Proxy | Purpose |
|---|---|---|---|---|
| A | `ostc-app.org` | `192.168.1.2` | ✅ Proxied (orange cloud) | Application |

Cloudflare proxy means:
- Public DNS resolves to Cloudflare IPs
- Cloudflare forwards traffic to `192.168.1.2:8080` (nginx on k3s-2, Flexible SSL)
- Cloudflare handles SSL (Flexible — HTTPS to user, HTTP to k3s-2)
- `server: cloudflare` in HTTP headers

---

## 🔄 Traffic flow

```
🌐 User → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → 192.168.1.2:8080 (k3s-2 nginx)
      → nginx proxy_pass http://192.168.1.50:8002
        → Service LoadBalancer (MetalLB)
          → sola-app pod (k3s-1 or k3s-2)

Alternative path (internal network):
http://192.168.1.1:8080 → nginx on k3s-1 → proxy_pass 192.168.1.50:8002
http://192.168.1.2:8080 → nginx on k3s-2 → proxy_pass 192.168.1.50:8002
http://192.168.1.50:8002 → direct to LoadBalancer
```

---

## 📜 Domain change history

| Period | Domain | Description |
|---|---|---|
| May 2026 | `sola-app.local` | Initial local domain (mDNS) |
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
2. Add A record: `@` → `192.168.1.10` (Proxied)
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

- **LoadBalancer IP** `192.168.1.10` is fixed — it does not change on restart
- **Nginx** on k3s-2 forwards to the MetalLB IP, not directly to pods
- **Cloudflare SSL** is "Full" — traffic between Cloudflare and nginx is HTTP (not encrypted), but only within the school network
- If you wanted **end-to-end HTTPS**, you would need certbot/letsencrypt on k3s-2
