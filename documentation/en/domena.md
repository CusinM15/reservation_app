🌐 **Language / Jezik:** [🇸🇮 Slovenščina](../domena.md) | [🇬🇧 English](domena.md)

---

> ⚠️ **Note:** IP addresses, passwords, email addresses, and other sensitive data
> in this documentation are replaced with examples. For actual values, check
> Kubernetes Secrets or contact the administrator.

---

# Domain

Current domain: **`ostc-app.org`** (Cloudflare proxied)

---

## 📋 Current DNS settings

| Type | Name | Value | Proxy | Purpose |
|---|---|---|---|---|
| A | `{{DOMAIN}}` | `{{K3S_2_IP}}` | ✅ Proxied (orange cloud) | Application |

Cloudflare proxy means:
- Public DNS resolves to Cloudflare IPs
- Cloudflare forwards traffic to `192.168.1.2` (k3s-2, port 80, Flexible SSL)
- Cloudflare handles SSL (Flexible — HTTPS to user, HTTP to k3s-2 on port 80)
- `server: cloudflare` in HTTP headers

---

## 🔄 Traffic flow

```
🌐 User → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → 192.168.1.2:80 (k3s-2)
      → Service LoadBalancer (MetalLB, 192.168.1.10:8002)
        → sola-app pod (k3s-1 or k3s-2)

Alternative path (internal network):
http://192.168.1.10 → direct to LoadBalancer
```

---

## 📜 Domain change history

| Period | Domain | Description |
|---|---|---|
| May 2026 | `sola-app.local` | Initial local domain (mDNS) |
| May 2026 | `ostc.si` | Old production domain |
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
2. Add A record: `@` → `192.168.1.2` (Proxied, k3s-2)
3. Wait for DNS propagation

### 2. Update BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

---

## 📌 Notes

- **LoadBalancer IP** `192.168.1.10` is fixed — it does not change on restart
- **Cloudflare SSL** is "Flexible" — HTTPS between user and Cloudflare, HTTP between Cloudflare and k3s-2 (within school network only)
- If you wanted **end-to-end HTTPS**, you would need certbot/letsencrypt on k3s-2
