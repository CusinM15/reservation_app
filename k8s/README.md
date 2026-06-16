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
│       ├── frp/
│       ├── ingress/
│       └── production-lb/
├── cluster/
│   └── metallb-config.yaml
└── secrets/
    └── README.md
```

## CronJob za dnevni backup

CronJob `sola-db-backup` teče ob **04:00 po času Johannesburga** (`Africa/Johannesburg`, SAST/UTC+2).
Manifest je v `app/base/sola-backup-cronjob.yaml`.

```bash
kubectl -n sola-app get cronjob sola-db-backup
kubectl -n sola-app describe cronjob sola-db-backup
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

Deploy z Ingressom:

```bash
kubectl apply -k k8s/app/overlays/ingress
```

Deploy za FRP/tunel varianto:

```bash
kubectl apply -k k8s/app/overlays/frp
```

Za pregled generiranih manifestov brez spreminjanja klasterja:

```bash
kubectl kustomize k8s/app/overlays/production-lb
kubectl kustomize k8s/app/overlays/ingress
kubectl kustomize k8s/app/overlays/frp
```
