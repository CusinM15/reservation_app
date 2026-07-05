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

## CronJob za dnevni k3s/Longhorn report

CronJob `sola-daily-report` teče ob **04:00 po času Ljubljane** (`Europe/Ljubljana`).
Report je razdeljen na tri read-only “agent” sekcije:

- `k3s agent`: nodi, podi, workloadi, cronjobi, warning eventi
- `Longhorn agent`: volumi, replike, degradacije, rebuildi, disk usage
- `node health / lifetime estimate agent`: heuristic ocena tveganja za posamezen node

Manifesti:

```text
app/base/sola-daily-report-cronjob.yaml
app/base/sola-reporter-serviceaccount.yaml
app/base/sola-reporter-clusterrole.yaml
app/base/sola-reporter-clusterrolebinding.yaml
```

RBAC je namerno read-only. CronJob ne bere logov in ne izvaja destructive ukazov.

```bash
kubectl -n sola-app get cronjob sola-daily-report
kubectl -n sola-app describe cronjob sola-daily-report
kubectl -n sola-app logs -l job-name=<job-name> --tail=100
```

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
