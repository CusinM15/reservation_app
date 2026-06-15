# Kubernetes Secreti

V tej mapi ne hranimo dejanskih skrivnosti. Secret `sola-secrets` mora obstajati v namespaceu `sola-app` pred deployom aplikacije.

Zahtevani ključi:

- `DATABASE_URL`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_FROM`
- `BACKUP_EMAIL`

Če Secret že obstaja, ga ne prepisuj z naključnimi vrednostmi. Posodobi samo manjkajoče ključe:

```bash
kubectl -n sola-app get secret sola-secrets
kubectl -n sola-app create secret generic sola-secrets \
  --from-literal=KLJUC='vrednost' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Za menjavo obstoječega ključa:

```bash
kubectl -n sola-app create secret generic sola-secrets \
  --from-literal=KLJUC='nova-vrednost' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Po spremembi Secretov ponovno zaženi deployment:

```bash
kubectl -n sola-app rollout restart deployment/sola-app
kubectl -n sola-app rollout status deployment/sola-app
```
