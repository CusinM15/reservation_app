[🇸🇮 Slovenščina](../k3s_setup.md) | [🇬🇧 English](k3s_setup.md)

---

# ☸️ **K3s Cluster Setup — ostc-app**

See the [Admin/DevOps Guide](admin_devops.md) for complete k3s installation instructions.

## Quick Installation

### First node (k3s-1, 193.2.171.250)

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb --disable=traefik" sh -
```

Save the token:
```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### Second node (k3s-2, 193.2.171.249)

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://193.2.171.250:6443 \
  K3S_TOKEN=<token> \
  sh -
```

### Verify

```bash
kubectl get nodes
kubectl get pods -A
```

## Post-Installation

### Install MetalLB

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
```

Configure IP pool:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 193.2.171.200-193.2.171.200
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-advertisement
  namespace: metallb-system
EOF
```

### Install Longhorn

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.7.1/deploy/longhorn.yaml
```

### Install CloudNativePG

```bash
kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.29/releases/cnpg-1.29.1.yaml
```
