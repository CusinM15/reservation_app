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
|---|---|---|---|---|---|
| A | `{{DOMAIN}}` | `{{LB_IP}}` | ✅ Proxied (orange cloud) | Application (via LoadBalancer) |
| A | `www` | `{{LB_IP}}` | ✅ Proxied (orange cloud) | WWW redirect |

Cloudflare proxy (orange cloud) means:
- Public DNS resolves to Cloudflare IPs (user sees Cloudflare edge)
- Cloudflare forwards traffic to `{{LB_IP}}` (port 80, Flexible SSL)
- Cloudflare handles SSL (Flexible — HTTPS to user, HTTP to LoadBalancer)
- LoadBalancer (MetalLB) receives traffic on port 80 and forwards to sola-app pods on port 8002
- If one node fails, MetalLB automatically moves `{{LB_IP}}` to the healthy node — **HA works without manual intervention**

---

## 🔄 Traffic flow

```
🌐 User → https://ostc-app.org
  → Cloudflare DNS → Cloudflare edge
    → Cloudflare proxy → {{LB_IP}}:80 (LoadBalancer, MetalLB)
      → sola-app Pod (k3s-1 or k3s-2) :8002

(No alternative paths — the architecture uses Cloudflare directly to the LoadBalancer.)
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
2. Add A record: `@` → `{{LB_IP}}` (Proxied, LoadBalancer MetalLB IP)
3. Wait for DNS propagation

### 2. Update BASE_URL

```bash
kubectl -n sola-app patch configmap sola-config --type merge \
  -p '{"data":{"BASE_URL":"https://nova-domena.si"}}'
kubectl -n sola-app rollout restart deployment/sola-app
```

---



## 📌 Notes

- **Cloudflare → LB IP** (`{{LB_IP}}`) — traffic goes directly to MetalLB
- **Cloudflare SSL** is "Flexible" — HTTPS between user and Cloudflare, HTTP between Cloudflare and LoadBalancer (`{{LB_IP}}:80`)
- **LoadBalancer** (MetalLB) listens on port 80 and forwards to sola-app container port 8002
- If you wanted **end-to-end HTTPS** (Cloudflare → origin), you would need certbot/letsencrypt and change SSL to "Full"

---

## 🏥 High Availability (HA)

### Why Cloudflare → LB IP?

| Scenario | Result |
|---|---|
| k3s-1 fails | MetalLB moves `{{LB_IP}}` to k3s-2, pod migrates → ✅ **HA works** |
| k3s-2 fails | MetalLB moves `{{LB_IP}}` to k3s-1, pod migrates → ✅ **HA works** |
| Both nodes fail | Application is unavailable → ❌ (no cross-cluster HA) |

**Cloudflare doesn't know which node is alive** — it simply sends traffic to `{{LB_IP}}`. MetalLB ensures this IP is always on a healthy node.

---


