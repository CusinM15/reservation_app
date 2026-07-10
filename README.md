🌐 **Language / Jezik:** [🇸🇮 Slovenščina](README.md) | [🇬🇧 English](documentation/en/README.md)

---

# Šolski App – Reservation & Assessment Management

Spletna aplikacija za OŠ Toneta Čufarja Jesenice za rezervacije prostorov (tablice, računalnica, ladja in učilnico za gospodinstvo) in napovedovanje ocenjevanj.

---

## ⚠️ Težava: Windows 10 ni več varen, Windows 11 ne dela na starih računalnikih

Na šoli imamo kar nekaj delujočih računalnikov, ki so prestari za Windows 11 (TPM 2.0, CPU zahteve), Windows 10 pa **od oktobra 2025 nima več varnostnih posodobitev**. Puščati jih na Windows 10 je tvegano.

**Možnosti:**

| Opcija | Opis |
|--------|------|
| **Linux Mint** | Najbolj "Windows-like" — če znaš delati v Windows, boš takoj domač. Lahek, dela na starih strojih. |
| **Zorin OS** | Še bolj podoben Windows (celo layout je isti). "Zorin Connect" poveže s telefonom. Prav tako lahek. |
| **Lokalni strežnik** | Eden od starih računalnikov postane strežnik — nanj namestiš Linux, gor zaženeš app in ga deliš po šoli. |

---

## 🖥️ Lokalni strežnik — bolj zahtevna pot

Če enega od starih računalnikov spremeniš v strežnik, dobiš polno kontrolo — app teče v šoli, podatki so lokalni, ni mesečnih stroškov. Je pa potrebno znanje:

- namestitev Linuxa
- Docker in docker-compose
- omrežne nastavitve (DHCP rezervacija, odprta vrata)
- vzdrževanje (posodobitve, backupi, odpravljanje napak)
- restart ob izpadu elektrike

Za vse to obstajajo **podrobna navodila** v [dokumentaciji](documentation/main.md).

---

## ☁️ Lažja varianta — najem storitve v oblaku

Ker lokalen strežnik zahteva kar precej znanja in rednega vzdrževanja, obstaja preprostejša rešitev: **app daš v oblak**. Tam za vse poskrbi ponudnik — strežnik, baza, backupi, varnost. Plačaš ~€7–15 na mesec in nimaš nobenega dela.

Več o tem v [migracija_oblak.md](documentation/migracija_oblak.md) — dokumentu, kjer so primerjave vseh opcij z natančnimi cenami in plusi/minusi.

> ℹ️ **Opomba:** To datoteko je 100%% generiral AI (Hermes Agent). Avtor (Matej) se na cloud storitve spozna bolj približno in ne jamči za legitimnost navedenih cen in storitev — je pa dober začetek za pogovor z nekom, ki se s tem ukvarja.

---

## 📚 Za tiste, ki bi radi sami postavili in vzdrževali app

Spisal sem kar dolga in **zelo podrobna navodila** — od namestitve na gol Linux, do k3s Kubernetes clustra, baze, backupov in reševanja težav. Najdeš jih v:

> **[documentation/main.md](documentation/main.md)** — celotna dokumentacija v slovenščini

---

---

## ☕ Podpri projekt

Če ti je aplikacija v pomoč, mi lahko kupiš kavo prek PayPalla:

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=TVKQZWNUEWMPQ)

---

**Avtor:** Matej Čušin  
