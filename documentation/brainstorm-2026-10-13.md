# 🧠 Brainstorm zapis — HA/nodi (Hetzner) in MDM za tablice

> Zapis pogovora (2026-10-13). **Brainstorm — ni odločitev, ni sprememb obstoječe kode.**
> Dopolnjuje `v_oblak.md`, `HA.md` in `intune_konkurenca.md` (teh ne spreminja).

---

## Del A — Nodi / Hetzner / hramba baze

**Vprašanje:** Ali moram nujno začeti s 3 nodi? Ali Hetzner skrbi za stalno
menjavo in hrambo baze, če pade? Koliko časa traja menjava — moram vsakič sam
postaviti nov stroj?

**Odgovori:**

1. **3 nodi niso obvezni za začetek.** 3 je priporočilo za *pravo HA* (1 ali 3;
   nikoli 2 — glej razdelek 4 v `v_oblak.md`). Za test/poceni je dovolj 1 node
   (ni HA).

2. **Hetzner ne skrbi za menjavo ali bazo sam.** Hetzner Cloud = gola
   infrastruktura (IaaS): da VM + diske. k3s, baza in njihov failover so tvoja
   odgovornost. Hetzner ne dvigne replike tvoje baze, če VM pade.

3. **Baza ob izpadu:** če je postavljena pravilno (CNPG, ≥3 instance = primary +
   replike čez node), ob izpadu noda z primary replika prevzame v ~1–2 min.
   Podatkov ne izgubiš. To je tvoj setup, ne Hetznerjev.

4. **Kako pogosto node crkne:** zelo redko — praktično ~1× na 1–2 leti ali manj.

5. **Ali moram sam postaviti nov node:** da — k3s ni managed k8s, torej VM
   ročno znova ustvariš in dodaš v cluster (`dodajanje-noda.md`). Delo ~15–30 min.
   A s 3 nodi en izpad ne ustavi appa → zamenjaš ob svojem času, brez panike.

6. **Če nočeš tega dela:** managed Kubernetes (Scaleway / DigitalOcean DOKS) ali
   managed baza (Neon / Supabase / Railway Postgres) → manj dela, dražje,
   podatki v tujem cloudu.

**TL;DR:** 3 node = en lahko pade, app dela naprej; bazo reši CNPG; zamenjava
redka, ~15–30 min. Hetzner sam ne skrbi za nič od tega.

---

## Del B — MDM konkurenca Intune: samo tablice + dokup

**Vprašanje:** Ali bi bilo simpl, da bi naredil samo za (Android) tablice in to
ponudil kot možen dokup — nadzor tablic, pravila za učence?

**Odgovori (skladno z `intune_konkurenca.md` §7):**

1. **Da — to je realna niša in najpametnejši obseg.** Samo Android tablice
   izpustijo Windows in Apple (najtežji platformi); ostane en protokol
   (Android Enterprise / AMAPI, brez lastnega odjemalca).

2. **Dokup k naročnini** (€/šola/leto ali €/tablico/leto) pomeni: ni nov izdelek,
   ni nov prodajni kanal — šola s tablicami plača doplačilo.

3. **Nadzor + pravila za učence** (kiosk, dovoljene aplikacije, blokada trgovine,
   osnovna politika geslo/posodobitve, oddaljena ponastavitev) = Faze 1–5 iz
   `intune_konkurenca.md` §5.

4. **Simpl za prodajo in obseg, NE za izvedbo.** AMAPI integracija, enrollment,
   ukazni kanal, revizija in MFA so še vedno pravi razvoj.

5. **Varnostni pogoj:** MFA za skrbnike + revizijska sled ukazov sta nujna, ker
   skrbnik naprav upravlja vse tablice.

6. **Vrstni red:** najprej Faza 0 (inventar + katalog politik — varno, poceni,
   vključeno) → šele ko dokup plačajo, Faze 1–5 (pravo upravljanje prek AMAPI).

7. **Odprto:** enota cene 150 €/leto + ali šole obvladajo Google račun naprav
   (GMS). Brez GMS Android-only dokup ni izvedljiv.

**TL;DR:** Android tablice + dokup = prava pot. Začni s Fazo 0 (inventar), pravo
upravljanje šele ob plačilu. Ena platforma, jasna niša, ampak izvedba ni trivialna.
