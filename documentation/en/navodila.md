[🇸🇮 Slovenščina](../navodila.md) | [🇬🇧 English](navodila.md)

---

# 📘 **General Admin Instructions — ostc-app**

## Server & Maintenance

### Server Access

```bash
# SSH access
ssh admin_os@193.2.171.250   # k3s-1
ssh admin_os@193.2.171.249   # k3s-2

# Sudo password (if needed): on first connection
```

### Regular checks

```bash
# Cluster health
kubectl get nodes
kubectl get pods -A | grep -v Completed

# Application
kubectl get pods -n sola-app -o wide
kubectl logs -n sola-app deployment/sola-app --tail=50

# Database
kubectl get pods -n sola -o wide
kubectl get cluster -n sola sola-db
```

### User management

**Via UI (Admin panel):**
- Navigate to https://ostc-app.org and log in as admin
- Admin panel → search/edit users, change roles, reset passwords

**Via import script:**
```bash
cd /home/admin_os/ostc-app_deli
python3 scripts/import_teachers.py --base-url https://ostc-app.org
```

### Restarting services

```bash
# Restart just the app
kubectl rollout restart -n sola-app deployment/sola-app

# Restart nginx
sudo systemctl reload nginx

# Full node restart (only when necessary!)
sudo reboot
```

## Troubleshooting

**App shows 502 Bad Gateway**
- Check if app pods are running: `kubectl get pods -n sola-app`
- Check if LoadBalancer is reachable: `curl -I http://193.2.171.200:8002`
- Restart app if needed: `kubectl rollout restart -n sola-app deployment/sola-app`

**App can't connect to database**
- Check database pod status: `kubectl get pods -n sola`
- Check database service: `kubectl get svc -n sola sola-db-rw`
- Verify credentials in secret: `kubectl get secret -n sola-app sola-secrets`

**Node not ready**
- Check node status: `kubectl get nodes`
- SSH into the node and check: `sudo systemctl status k3s`
- Restart k3s if needed: `sudo systemctl restart k3s`

**Longhorn issues**
- Port-forward to dashboard: `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80`
- Check disk usage and replica status
- Enable replica-auto-balance if disks are unbalanced

## Network

### Nginx config (both nodes)

```bash
sudo nano /etc/nginx/sites-available/default
sudo nginx -t && sudo systemctl reload nginx
```

### Cloudflare

- Dashboard: https://dash.cloudflare.com
- DNS record: `ostc-app.org` → A → `193.2.171.200` (proxied)
- SSL/TLS: Full (strict)
