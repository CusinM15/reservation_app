# Mail lastniku domene ostc.si

**Zadeva:** Prošnja za poddomeno sola-app.ostc.si

---

```text
Zdravo,

na OŠ Toneta Čufarja smo vzpostavili spletno aplikacijo za
rezervacijo prostorov (računalnica, tablice, ladja) in vodenje
ocenjevanj. Aplikacija teče na našem k3s clusterju, dostopna
je interno na http://193.2.171.200:8002.

Trenutno smo jo objavili prek Cloudflare Tunela na poti
https://ostc.si/solski-app, vendar to povzroča težave s
pravilnim generiranjem URL-jev (CSS, redirecti, reset gesla).

Prosim, če lahko ustvariš **poddomeno**:

    sola-app.ostc.si → 193.2.171.200 (A zapis)

ali če uporabljate Cloudflare DNS, CNAME:

    sola-app.ostc.si → <tunnel-id>.cfargotunnel.com

S to spremembo bo aplikacija delovala na korenu domene in
vsi linki bodo pravilni.

Hvala in lep pozdrav,
[IME]
```

---

## Kaj spremeniti v kodi po ustvaritvi poddomene

### sola-config.yaml

```yaml
  BASE_URL: "https://sola-app.ostc.si"
```

### .env

```env
BASE_URL=https://sola-app.ostc.si
```

### cloudflared config (če uporabljaš tunnel)

V `~/.cloudflared/config.yml`:

```yaml
  - hostname: sola-app.ostc.si
    service: http://193.2.171.200:8002
```

Nato:

```bash
cloudflared tunnel route dns solski-app sola-app.ostc.si
kubectl apply -f sola-config.yaml
kubectl rollout restart deployment/sola-app -n sola-app
```
