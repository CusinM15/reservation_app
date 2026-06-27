[🇸🇮 Slovenščina](../domena.md) | [🇬🇧 English](domena.md)

---

# 🏗️ **Domain & Network — ostc-app**

## DNS & Cloudflare

**Domain:** `ostc-app.org`  
**Provider:** Cloudflare (proxied)

### DNS Records

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | `ostc-app.org` | `193.2.171.200` | ✅ Proxied (orange cloud) |

### SSL/TLS

- **Mode:** Full (strict)
- **Origin certificate:** self-signed on k3s-1 nginx
- Cloudflare terminates SSL at edge, then re-encrypts to origin

### Cloudflare Settings

- **Always Use HTTPS:** ON
- **Automatic HTTPS Rewrites:** ON
- **Minimum TLS Version:** 1.2
- **Browser Cache TTL:** 4 hours

## Nginx

Nginx runs on **both nodes** as a reverse proxy.

### Config location

```bash
/etc/nginx/sites-available/default   # k3s-1 + k3s-2
```

### Configuration

```nginx
server {
    listen 80;
    server_name ostc-app.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ostc-app.org;

    ssl_certificate     /etc/nginx/ssl/ostc-app.org.pem;
    ssl_certificate_key /etc/nginx/ssl/ostc-app.org.key;

    location / {
        proxy_pass http://193.2.171.200:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Testing & reload

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## MetalLB (LoadBalancer)

**IP Pool:** `193.2.171.200`  
**Mode:** L2 Advertisement (layer2)

```bash
# Check MetalLB status
kubectl get pods -n metallb-system
kubectl get svc -n sola-app sola-app
```

## Network Topology

```
Internet
    │
    ▼ Cloudflare
    │
    ├── k3s-1:443 (nginx SSL)
    │       │
    │       ▼ LB 193.2.171.200:8002
    │       │
    │       ├── pod:k3s-1
    │       └── pod:k3s-2
    │
    └── k3s-2:8080 (nginx)
            │
            ▼ LB 193.2.171.200:8002
            │
            ├── pod:k3s-1
            └── pod:k3s-2
```
