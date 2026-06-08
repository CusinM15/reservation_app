# Stanje k3s klustra — 8. 6. 2026

## Workerji (1)
- k3s-1 (193.2.171.250) — worker — Ready

## Master (1)
- k3s-2 (193.2.171.249) — control-plane — Ready

## Longhorn
- Vsi Longhorn podi Running (CSI, instance-manager, driver-deployer)
- longhorn-ui: 0/0 (ni pognan)
- Volumen (sola-postgresql, 10 GB): attached, healthy
- Število replik: 2 (1 na k3s-1, 1 na k3s-2) — obe running
- StorageClass numberOfReplicas: 2

## Aplikacijske replike
- sola-app: 1 replica (k3s-1), HPA 1–3, CPU 8%/70%
- sola-postgresql: 1 replica (StatefulSet, k3s-1)

## Skupaj
30 aktivnih podov. Vse teče normalno.
