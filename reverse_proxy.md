# Reverse proxy: ostc.si/solski-app → http://193.2.171.200:8002

Ta dokument pojasni, kako objaviti aplikacijo (LoadBalancer servis v k3s clustru,
dostopen interno na `http://193.2.171.200:8002`) pod javnim URL-jem
`https://ostc.si/solski-app`, brez sudo pravic na gostitelju, ki gosti domeno.

Glavna ovira: master in worker nimata javnega IP-ja, do njih z interneta ni
direktnega dostopa, in **nimaš root-a** na stroju kjer teče primarni
web server domene ostc.si.

Rešitev: **Cloudflare Tunnel (cloudflared)** — zažene se kot navaden uporabnik
iz home direktorija, vzpostavi odhodno TLS povezavo do Cloudflare, in objavi
notranji servis pod tvojo (sub)domeno. Brez odprtih vrat na firewall-u, brez
sudo, brez certifikatov za upravljanje.

Spodaj je tudi **plan B s Caddy + ngrok-like alternativo (zrok)** za primer, da
Cloudflare-a ne moreš/ne smeš uporabiti.

> Pomembna opomba o poti `/solski-app`:
> Cloudflare Tunnel sam po sebi mapira **subdomeno → notranji servis**, ne
> mapira poljubne podpoti pod glavno domeno. Zato sta priporočena dva pristopa:
>
> **(A)** Uporabi **subdomeno** `solski.ostc.si` ali `app.ostc.si` (najbolj
>     enostavno, najbolj zanesljivo). Aplikacija ostane na rootu `/`, vsi linki
>     v predlogah delujejo brez sprememb.
>
> **(B)** Vztrajaj na poti `ostc.si/solski-app` — to zahteva, da **obstoječi
>     reverse proxy** na ostc.si (Apache/Nginx, ki ga vzdržuje admin domene)
>     proxy_pass-a `/solski-app/*` na URL Cloudflare tunela. Brez sudo te poti
>     ne moreš sam vzpostaviti, ker je dodajanje location bloka admin opravilo.
>     Druga možnost: pri **Cloudflare-u** (če je ostc.si že na CF) lahko v Page
>     Rules / Rulesetih nastaviš redirect/rewrite z `ostc.si/solski-app/*` na
>     `solski.ostc.si/*` — to **ne** zahteva sudo.
>
> Spodnja navodila gredo po varianti **A (subdomena)** kot privzeti, varianta
> B je opisana na koncu kot dodatek.

---

## 0) Preverbe pred začetkom

```bash
# Aplikacija mora biti dosegljiva lokalno:
curl -sS http://193.2.171.200:8002/health
# Pričakovano: {"status":"ok","version":"0.1.0"}

# Cluster IP servisa:
kubectl get svc -n sola-app
# sola-app  LoadBalancer  10.43.x.x  193.2.171.200  8002:30329/TCP
```

Če `/health` ne odgovori, najprej popravi to (glej app/main.py, kubectl logs).

---

## 1) DNS — kaj točno vnesti pri registrarju

Predpostavka: domena `ostc.si` je že na **Cloudflare** name-serverjih ali pa
jo lahko prestaviš. Če ostane na drugem DNS-ju, Cloudflare Tunnel ne deluje
(tunel zahteva, da Cloudflare upravlja DNS zapis).

### 1a) Če ostc.si še NI na Cloudflare-u

1. Brezplačno se registriraj na https://dash.cloudflare.com.
2. **Add site → ostc.si → Free plan**.
3. CF ti pokaže dva nameserverja, npr. `arnold.ns.cloudflare.com` in
   `martha.ns.cloudflare.com`. Pri registrarju domene (npr. Arnes / register.si
   / GoDaddy) **zamenjaj NS zapise** z njihovima.
4. Počakaj 5 min – 24 h, dokler Cloudflare ne potrdi.

Vsi obstoječi DNS zapisi za ostc.si (A, MX za mail, TXT za SPF…) **morajo**
biti prej skopirani v CF dashboard, sicer pade web/mail. Cloudflare običajno
sam uvozi obstoječe zapise — preglej jih.

### 1b) Ko ostc.si TEČE na Cloudflare

DNS zapisa za naš tunnel **ne ustvarjaš ročno** — to naredi `cloudflared`
sam, ko zaženeš `cloudflared tunnel route dns ...` (glej spodaj). Avtomatsko
nastavi CNAME `solski.ostc.si → <UUID>.cfargotunnel.com` z oranžnim oblačkom
(proxied).

Edina ročna nastavitev, ki jo lahko narediš zdaj v CF dashboardu:
- **SSL/TLS → Overview → Full** (ne Flexible — full=CF zahteva TLS proti origin-u,
  ampak ker tunel je TLS, je v redu).
- **SSL/TLS → Edge Certificates → Always Use HTTPS = ON**.

---

## 2) Namestitev cloudflared **brez sudo** v home

```bash
mkdir -p ~/bin ~/.cloudflared
cd ~/bin

# AMD64 (preveri arch z `uname -m` -> x86_64)
curl -L -o cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared

# Dodaj ~/bin v PATH (če še ni)
grep -q 'HOME/bin' ~/.bashrc || echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

cloudflared --version    # potrditev
```

---

## 3) Avtentikacija in tunel

```bash
# Odpre URL v brskalniku, prijaviš se v Cloudflare, izbereš domeno ostc.si:
cloudflared tunnel login
# → shrani cert v ~/.cloudflared/cert.pem

# Ustvari tunel z imenom (po želji):
cloudflared tunnel create solski-app
# Izpiše npr. "Created tunnel solski-app with id 1234abcd-..."
# in zapiše credentials v ~/.cloudflared/<UUID>.json

# DNS zapis (CF avtomatsko ustvari CNAME solski.ostc.si → <UUID>.cfargotunnel.com):
cloudflared tunnel route dns solski-app solski.ostc.si
```

---

## 4) Konfiguracija tunela

Ustvari `~/.cloudflared/config.yml`:

```yaml
tunnel: solski-app
credentials-file: /home/<TVOJ_USER>/.cloudflared/<UUID>.json

ingress:
  - hostname: solski.ostc.si
    service: http://193.2.171.200:8002
    originRequest:
      # podaljšaj timeout-e za počasne strani / poročila
      connectTimeout: 30s
      noTLSVerify: false
  # catch-all (obvezen kot zadnja vrstica)
  - service: http_status:404
```

Zamenjaj `<TVOJ_USER>` in `<UUID>`. UUID najdeš s `cloudflared tunnel list`.

Test:
```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run solski-app
# v drugem terminalu:
curl -sS https://solski.ostc.si/health
# pričakovano: {"status":"ok","version":"0.1.0"}
```

Če dela, ustavi z Ctrl+C in nadaljuj v točki 5 za trajni zagon.

---

## 5) Trajni zagon **brez sudo** — `systemd --user`

systemd-user-lingering ti omogoča, da servis teče tudi ko nisi prijavljen
v shell (Ubuntu 24.04 ima privzeto omogočeno za uporabnike z UID >= 1000;
če ne, lahko `loginctl enable-linger $USER` zahteva root **enkratno** —
to lahko admin naredi enkrat in vse ostalo upravljaš sam).

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/cloudflared.service <<'EOF'
[Unit]
Description=Cloudflare Tunnel za solski.ostc.si
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/bin/cloudflared tunnel --config %h/.cloudflared/config.yml run solski-app
Restart=on-failure
RestartSec=5s
# omeji loge
StandardOutput=append:%h/.cloudflared/tunnel.log
StandardError=append:%h/.cloudflared/tunnel.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now cloudflared
systemctl --user status cloudflared
```

Če `loginctl enable-linger` ni omogočen, alternativa **screen/tmux**:
```bash
screen -dmS tunnel ~/bin/cloudflared tunnel --config ~/.cloudflared/config.yml run solski-app
# pripni nazaj:
screen -r tunnel
# odpni: Ctrl-A d
```

Slabost screen-a: po reboot-u stroja ne zažene samodejno. Zato je
systemd --user veliko boljša izbira; če admin pristane, naj enkrat požene:
```bash
sudo loginctl enable-linger <TVOJ_USER>
```

---

## 6) Testiranje

```bash
# Health endpoint:
curl -sS https://solski.ostc.si/health
# {"status":"ok","version":"0.1.0"}

# Statična stran (login):
curl -sSI https://solski.ostc.si/auth/login
# HTTP/2 200
# server: cloudflare

# Iz brskalnika:
#   https://solski.ostc.si        → redirect na login
#   https://solski.ostc.si/health → JSON

# Tunnel log:
tail -f ~/.cloudflared/tunnel.log

# Status:
systemctl --user status cloudflared
cloudflared tunnel info solski-app
```

---

## 7) Posodobi BASE_URL v ConfigMap in restartaj deployment

`BASE_URL` se uporablja v emailih (reset gesla), zato mora odražati javni URL:

```bash
# Pokaži trenutno vrednost:
kubectl get cm sola-config -n sola-app -o jsonpath='{.data.BASE_URL}'

# Posodobi (subdomenski pristop — varianta A):
kubectl patch configmap sola-config -n sola-app \
  --type merge \
  -p '{"data":{"BASE_URL":"https://solski.ostc.si"}}'

# ali, če greš po varianti B (path pod glavno domeno):
# kubectl patch configmap sola-config -n sola-app \
#   --type merge \
#   -p '{"data":{"BASE_URL":"https://ostc.si/solski-app"}}'

# Restartaj deployment, da poberejo novo vrednost:
kubectl rollout restart deployment/sola-app -n sola-app
kubectl rollout status deployment/sola-app -n sola-app

# Verifikacija (preveri da se /health še vedno odzove):
curl -sS https://solski.ostc.si/health
```

---

## Varianta B: pot `ostc.si/solski-app` (path-based)

Če je nujno, da pot **ne** vsebuje subdomene, ampak je oblike
`https://ostc.si/solski-app/...`, potrebuješ enega od teh:

### B1) Cloudflare Rewrite (priporočeno, brez sudo)

Cloudflare dashboard:
1. **Rules → Transform Rules → Rewrite URL → Create rule**
2. Pogoj: `(http.request.uri.path matches "^/solski-app(/.*)?$")` in
   `(http.host eq "ostc.si")`
3. Akcija: **Rewrite to → Dynamic → URI path**:
   `regex_replace(http.request.uri.path, "^/solski-app", "")`
4. **Origin Rules → Set Origin** (ali samostojen Worker), da se origin host
   nastavi na `solski.ostc.si`. Ali pa enostavneje:
5. **Page Rules** → `ostc.si/solski-app/*` → **Forwarding URL (301)** →
   `https://solski.ostc.si/$1`. To **ni** transparent proxy (uporabnik vidi
   spremembo URL-ja), je pa najpreprostejše.

Za _transparent_ podpoti pod glavno domeno priporočam Cloudflare Workers
script (≈10 vrstic JS-ja); lahko ti ga pripravim posebej.

### B2) Admin domene doda location v Apache/Nginx (zahteva sudo na njihovi strani)

```nginx
# v server bloku za ostc.si na njihovem nginx-u:
location /solski-app/ {
    proxy_pass https://solski.ostc.si/;
    proxy_set_header Host solski.ostc.si;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_redirect / /solski-app/;
}
```

Aplikacija pa potrebuje **root_path** nastavitev v uvicornu, da generira
pravilne URL-je v predlogah:

```bash
# v Dockerfile/start command:
# uvicorn app.main:app --host 0.0.0.0 --port 8002 --root-path /solski-app
```

---

## Plan B: zrok (alternativa, če ne moreš Cloudflare)

[zrok](https://zrok.io) je open-source alternativa ngrok-u, brezplačni račun.
Tudi tunelira odhodno, brez sudo.

```bash
mkdir -p ~/bin && cd ~/bin
curl -sL https://github.com/openziti/zrok/releases/latest/download/zrok_linux_amd64.tar.gz | tar xz
# Registracija na https://api.zrok.io, dobiš token
./zrok invite               # ali enable z gostujočim accountom
./zrok enable <token>
./zrok reserve public --backend-mode proxy http://193.2.171.200:8002
# dobiš stalno javno povezavo solski-xy.share.zrok.io
```

Pomanjkljivost: javni URL je oblike `<random>.share.zrok.io`, ni tvoje domene.
Lahko pa nanj kažeš s CNAME `solski.ostc.si` (Cloudflare DNS, ne tunnel) —
ampak takrat se izgubi HTTPS na lastni domeni (CF Universal SSL pokrije samo
do origin-a, zrok do svojega CN-ja). Cloudflare Tunnel je za tvoj scenarij
boljši.

---

## Diagnostika

| Simptom | Najverjetnejši vzrok | Test/rešitev |
|---|---|---|
| `503 Service Unavailable` od cloudflared | App ne odgovarja na 193.2.171.200:8002 | `curl http://193.2.171.200:8002/health` na masterju |
| `1033 Argo Tunnel error` | Tunel ne teče | `systemctl --user status cloudflared` |
| DNS ne resolva | CNAME ni nastavljen | `cloudflared tunnel route dns solski-app solski.ostc.si` ponovi |
| Statika (CSS/JS) 404 | App predloge generirajo absolutne poti, ki ne ustrezajo varianti B | Uporabi varianto A (subdomena) ali nastavi `--root-path` |
| Login redirect loop | Cookie `user_id` ne pride nazaj | V CF: **Rules → Origin Rules → Host header** preveri; v config.yml dodaj `noHappyEyeballs: true` |
| Počasen odziv | Origin v sloveniji, CF edge v Frankfurtu | Privzeto OK; preveri DNS overrides |

Logi:
```bash
tail -100 ~/.cloudflared/tunnel.log
kubectl logs -n sola-app -l app=sola-app --tail=50
```
