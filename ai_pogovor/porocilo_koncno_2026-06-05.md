## Končno poročilo — 5. junij 2026

### Nodi
| Node | Vloga | IP | OS |
|---|---|---|---|
| **k3s-1** | worker | 193.2.171.250 | Ubuntu 24.04 |
| **k3s-2** | control-plane | 193.2.171.249 | Ubuntu 24.04 |

### Aplikacija
| Komponenta | Status | Detajli |
|---|---|---|
| **sola-app pod** | ✅ 1/1 Running | na k3s-2, IP: 10.42.1.12 |
| **sola-postgresql** | ✅ 1/1 Running | na k3s-1, IP: 10.42.1.13 |
| **HPA** | ✅ Aktivno | min=1, max=3, CPU=9%/70% |
| **LoadBalancer** | ✅ 193.2.171.200:8002 | Metallb |

### Dostop do aplikacije
```
🌐 https://marvel-priced-ethernet-baths.trycloudflare.com/auth/login
   ↓ Cloudflare Tunnel (http2, service enabled on reboot)
   k3s-1: cloudflared → 193.2.171.200:8002
   ↓
   Metallb → sola-app pod (k3s-2)
   ↓
   sola-postgresql (k3s-1)
```

### Odstranjeno
| Storitev | Prej | Zdaj |
|---|---|---|
| **Twingate Docker** (k3s-1) | ✅ Running | ❌ Odstranjen |
| **Twingate K8s** (namespace) | ✅ Running | ❌ Namespace zbrisan |
| **Oracle VM** | Bila je posrednik | ❌ Popolnoma odstranjena |
| **Hitrost domena** | Bila v uporabi | ❌ Ni več v arhitekturi |

### Cloudflare Tunnel
| Storitev | Status |
|---|---|
| **cloudflared** nameščen | ✅ Verzija 2026.5.2 |
| **systemd servis** | ✅ Enabled, restart: always |
| **Protokol** | http2 (ker QUIC blokira firewall) |
| **URL** | `https://marvel-priced-ethernet-baths.trycloudflare.com` |
| **Omejitev** | Quick tunnel — URL se spremeni ob restartu |

### Kaj še lahko narediš
1. **Na dpdns.org** nastavi `rezervacije.dpdns.org` kot CNAME ali HTTP redirect na `marvel-priced-ethernet-baths.trycloudflare.com`
2. **Za trajno domeno** dodaj pravo domeno v Cloudflare (kupi prek Cloudflare za ~8-12€/leto) — potem lahko nastaviva named tunnel s fiksnim URL-jem
