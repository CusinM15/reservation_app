# Spiši čimbolj preprosta in natančna navodila, kako postaviti ta app

Ta navodila daj kot README.md na repozitoriju git@github.com:os-tc-jesenice/ostc-app_deli.git poleg teh navodil daj na ta repozitorij tudi kopijo aplikacije s prazno tabelo in .env naj bo zgolj pokazan kaj rabijo nastaviti.

Najprej preveri kaj vse ti  sedaj rabiš, da app teče in le to ponotranji, da si boš lažje priklical kaj rabiva.
App lahko postaviva na 3 načine, pri dveh od teh variant se da dokaj okej uporabiti tudi windovs, toda glede na to, da imate zelo verjetno več računalnikov, ki so "preslabi" za windovs 11, se mi zdi uporaba Ubuntu server 24 najbolj primeren OS.
- Prvi način zgolj na en računalnik (recimo v zbornici) clonirate repozitorij (dodaj navodila za cloniranje github repoja) in potem zgolj na temu računalniku dostopajo do app-a na http://localhost:(mislim da je tu še port)
- Drugi način je postavitev mDNS, potem bi na določenem delu omrežja (zaradi Arnes pravil, dela zgolj na delu) delal http://hostname.local (tu popravi/dopolni)
**Pri teh dveh metodah načeloma lahko dostopamo do app-a tudi direktno preko ip-a, kar odsvetujem (dodaj pridigo zakaj ne preko ip**
**Poleg tega na te dva načina priporočam da se app zažene zgolj kot uvicorn app, docker je namenjen za kubernetes, ne pozabi, da lahko install-amo knjižnice potrebujemo venv (dodaj v navodila tudi to)**
- Še zadnja varianta pa kubernetes clouster (k3s - povej kaj je kubernetes in kaj je j3s in zakaj bi to uporabil), pri tej varianti se skoncentrirajmo na Ubuntu server OS:
    - Daj navodila za nastavitev statičnega ip-a
    - Podaj tudi nastavitev, da računalnik dela tudi če je zaprt (da laptop postane kot server)
    - Razloži kaj je ssh in kako se ga upporablja, saj le to priporočam za uporabo
Potem so tu pomembne stvari pri nastavitvah cloustra, priporočam več kot en računalnik (tu povej kaj vse mora vsebovati en node, da ima ubistvu workerja, masterja, longhorn in tudi loadballancer), saj če boste uporabljali stare računalnike bodo le tej verjetno hitreje "crknili" kot novi, torej je optimalno, da imate vsaj 2 računalnika da ob primeru da en ne dela app ne "pade dol".
Dodati nov računalnik v že obstoječ cloustre (tu podrobna navodila kako dodati nov računalnik v clouster).
Tu povej cronjob-e, ki jih imam jaz v tem clousterju in zakaj je to fajn in kako le to nastaviti.
Za konec povej tudi da obstajajo ai agentje Hermes, Jcode etc. ki lahko zelo olajšajo vzdrževanje app-a, tako da daj tudi povezavo do git repoja od hermes in dodaj par primerov uporabe in kako le to nastaviti, povej tudi da claude žre denar kod nevem kaj, deepseek je pa poceni in kar dolgo zdrži denar.
Poleg tega me "podpiši" da se ve da je avtor app-a Matej Čušin.
