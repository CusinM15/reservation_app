# Kubernetes/k3s manifesti

Vsa Kubernetes YAML konfiguracija je zbrana tukaj. Osnovni objekti so v `app/base/`, variante izpostavitve servisa pa so v `app/overlays/`.

## Struktura

```text
k8s/
├── app/
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── sola-configmap.yaml
│   │   ├── sola-deployment.yaml
│   │   ├── sola-service.yaml
│   │   └── sola-backup-cronjob.yaml
│   └── overlays/
│       └── production-lb/
├── cluster/
│   └── metallb-config.yaml
└── secrets/
    └── README.md
```

## CronJob za dnevni backup

CronJob `sola-db-backup` teče ob **04:00 po času Ljubljane** (`Europe/Ljubljana`).
Manifest je v `app/base/sola-backup-cronjob.yaml`.

```bash
kubectl -n sola-app get cronjob sola-db-backup
kubectl -n sola-app describe cronjob sola-db-backup
```

## CronJob za varnostne kopije (sola-db-backup)

CronJob `sola-db-backup` teče ob **04:00 po času Ljubljane** (`Europe/Ljubljana`).
Za **vsako šolo posebej** sestavi `.sql` varnostno kopijo z izključno podatki te šole in jo
pošlje na naslov te šole (`BACKUP_EMAIL` v nastavitvah šole, sicer `ADMIN_EMAIL`).

Manifest:

```text
app/base/sola-backup-cronjob.yaml
```

Job uporablja `envFrom: secretRef: sola-secrets` (kot deployment), da prejme tudi `SECRET_KEY` —
brez njega aplikacija ob importu pade in job bi spodletel (to se je zgodilo prejšnji različici).

```bash
kubectl -n sola-app get cronjob sola-db-backup
kubectl -n sola-app logs -l job-name=<job-name> --tail=100
# ročni preizkus (po koncu job izbriši, da ostane čisto):
kubectl -n sola-app create job sola-backup-test --from=cronjob/sola-db-backup
```

**Opomba (2026-09-23):** CronJob `sola-daily-report` (dnevno poročilo o k3s/Longhorn) je bil
odstranjen na zahtevo uporabnika — skupaj z manifestom in vnosom v kustomizaciji. Objektov RBAC
(`sola-reporter-*`) in skripta `scripts/daily_report.py` ta sprememba ne briše.

## Secret

Občutljivih vrednosti ne shranjujemo v repozitorij. Pred deployom ustvari Secret:

```bash
kubectl -n sola-app create secret generic sola-secrets \
  --from-literal=DATABASE_URL='postgresql://sola:<geslo>@postgres:5432/sola' \
  --from-literal=MAIL_USERNAME='<uporabnik>' \
  --from-literal=MAIL_PASSWORD='<geslo>' \
  --from-literal=MAIL_SERVER='mail.arnes.si' \
  --from-literal=MAIL_PORT='587' \
  --from-literal=MAIL_FROM='<mail@domena.si>' \
  --from-literal=BACKUP_EMAIL='<backup@domena.si>'
```

Podrobneje glej `secrets/README.md`.

## Deploy

MetalLB IP pool uporabi enkrat, če ga cluster še nima:

```bash
kubectl apply -f k8s/cluster/metallb-config.yaml
```

Deploy z LoadBalancer servisom:

```bash
kubectl apply -k k8s/app/overlays/production-lb
```

Za pregled generiranih manifestov brez spreminjanja klasterja:

```bash
kubectl kustomize k8s/app/overlays/production-lb
```
