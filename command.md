=== K3S-3 FIX — WORKING COMMANDS (no backslashes) ===

1. STOP + CLEAN:
   sudo systemctl stop k3s
   sudo rm -rf /var/lib/rancher/k3s/server/db /etc/rancher/k3s/k3s.yaml
   sudo rm -f /etc/systemd/system/k3s.service.env

2. FIX SERVICE FILE (Python — avoids backslash issues):
   sudo python3 /tmp/fix-backslash.py

3. VERIFY FIX:
   cat /etc/systemd/system/k3s.service | tail -2

4. REBUILD K3S (as control-plane server):
   curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.35.5+k3s1 sh -s - server --cluster-cidr=10.42.0.0/16 --service-cidr=10.43.0.0/16 --server https://193.2.171.250:6443 --token 'K10126dfa574bbc9644fd63c1534b24a41d9b4c7e4a35d49e5771b35e7d213b8f1e::server:2d4fc811b3447e13eabf305d8e59d19a' --disable=traefik --disable=servicelb --write-kubeconfig-mode=644 --node-ip=193.2.171.251

5. START + RELOAD:
   sudo systemctl daemon-reload
   sudo systemctl start k3s

6. WAIT (60s for etcd init):
   sleep 60

7. FIX KUBECONFIG (if localhost):
   sudo sed -i 's|https://127.0.0.1:6443|https://193.2.171.250:6443|g' /etc/rancher/k3s/k3s.yaml
   sudo chmod 644 /etc/rancher/k3s/k3s.yaml
   sudo chown admin_os:admin_os /etc/rancher/k3s/k3s.yaml

8. VERIFY:
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   kubectl get nodes -o wide
