# Stanje po nastavitvi — k3s kluster

## Nodi

| Node | IP | Vloge | Taints |
|------|----|-------|--------|
| k3s-1 | 193.2.171.250 | worker | brez |
| k3s-2 | 193.2.171.249 | control-plane | brez |

---

## MetalLB

- **Obseg IP-jev:** 193.2.171.200 → 193.2.171.210 (IPAddressPool: metallb-system/default-pool)
- **L2Advertisement:** metallb-system/default-advertisement (vsa vmesnika)
- **Dodeljen IP za sola-app:** **193.2.171.200**
  - Service: LoadBalancer, ClusterIP: 10.43.122.112
  - Port: 8002/TCP → nodePort 30329

---

## Longhorn

| Volumen | Stanje | Robustnost | Velikost | Node | Replike |
|---------|--------|-----------|----------|------|---------|
| pvc-3c14c333... (PostgreSQL) | attached | healthy | 10 Gi | k3s-1 | 2 (1 na k3s-1, 1 na k3s-2) |

Vsi Longhorn podi (21/21) Running.

---

## Aplikacija

| Pod | Namespace | Status | Node |
|-----|-----------|--------|------|
| sola-app-649bbbfb9d-jmmvg | sola-app | Running (1/1) | k3s-2 |
| sola-postgresql-0 | sola | Running (1/1) | k3s-1 |

- HPA: sola-app, 1–3 replike, trenutno 1, CPU 8%/70%
- CronJob: sola-db-backup (vsak dan ob 03:00)
- **Dostopna na:** http://193.2.171.200:8002
