#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/cluster_report.py — celovito status poročilo k3s clustra
# (nodi + app + git + Cloudflare tunel) v markdown.
#
# VSE se nanaša na PRIVAT repo CusinM15/reservation_app_sell (ne na javni
# reservation_app, ki je samo deploy-mirror). Report shrani v `reports/`
# (latest.md + timestamp kopija) in ga commit+push-a na origin (privat).
#
# Dva načina zbiranja:
#   --mode host (default, teče na uporabnikovi mašini):
#       • nodi:  node-dashboard API http://127.0.0.1:9118 (basic auth)
#       • k8s:   kubectl prek SSH na node1 (deploy@62.84.176.42, kubeconfig 644)
#       • git:   LOKALNI git repo (origin = privat sell) — ne javni GH API
#       • CF:    deploy/logi cloudflared (kubectl) + e2e curl-i
#   --mode pod (teče v app podu, klic gumba "Pošlji zdravje/stanje clustra"):
#       • k8s:   in-cluster kubernetes client (RBAC sola-app-monitoring)
#       • nodi:  node-exporter :9100 direktno na vsakem nodu (kot node_report.py)
#       • GH:    REST API s tokenom (env GITHUB_TOKEN), push prek Contents API
#
# Uporaba:
#   python3 scripts/cluster_report.py             # host: zgeneriraj + commit + push
#   python3 scripts/cluster_report.py --no-push  # host: samo zgeneriraj + izpiši
#   python3 scripts/cluster_report.py --mode pod [--no-push]  # v podu
#
# Odvisnosti: host = Python stdlib + `ssh` + `curl` + `git` na mašini;
#             pod  = python kubernetes + requests (v requirements.txt).
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---- konfiguracija -----------------------------------------------------
# (dash_name, ip, hostname) — usklajeno z node-dashboard inventory-jem
NODES = [
    ("sola-node1", "62.84.176.42", "vmi3670013"),
    ("node2", "173.212.229.60", "vmi3676419"),
    ("node3", "169.58.173.86", "vmi3690638"),
]
IP_BY_HOST = {h: ip for _, ip, h in NODES}
HOST_BY_IP = {ip: h for _, ip, h in NODES}
KUBCFG_SSH = "deploy@62.84.176.42"          # gateway za kubectl (node1)
KUBECTL = "kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml"
DASH = "http://127.0.0.1:9118"
DASH_PW_FILE = Path.home() / ".hermes" / ".dashboard-pw.txt"
GH_REPO = "CusinM15/reservation_app_sell"   # PRIVAT — vse se nanaša na ta repo
ORIGIN = "origin"                           # privat reservation_app_sell
GIT_NAME, GIT_MAIL = "Matej", "matej.cusin@proton.me"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", KUBCFG_SSH]
NOW = dt.datetime.now()
GH_API = f"https://api.github.com/repos/{GH_REPO}"
GH_BLOB = f"https://github.com/{GH_REPO}/blob/main"


def sh(args: list[str], cwd: Path | None = None, timeout: int = 90) -> str:
    r = subprocess.run(args, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}… rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def ssh_cmd(cmd: str, timeout: int = 60) -> str:
    return sh(SSH + [cmd], timeout=timeout)


def kubectl(args: str, timeout: int = 60) -> str:
    return ssh_cmd(f"{KUBECTL} {args}", timeout=timeout)


def _dash_req(path: str, method: str = "GET", timeout: int = 90) -> dict:
    pw = DASH_PW_FILE.read_text().strip()
    req = urllib.request.Request(DASH + path, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(
        f"matej:{pw}".encode()).decode())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def dash_health(node_id: str) -> dict:
    return _dash_req(f"/api/nodes/{node_id}/health", method="POST")


def curl_code_ms(url: str, timeout: int = 15) -> tuple[str, int | None]:
    """(http_code, ms) — brez redirect follow (307 ostane 307)."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-m", str(timeout),
             "-w", "%{http_code} %{time_total}", url],
            capture_output=True, text=True, timeout=timeout + 5)
        code, t = r.stdout.strip().split()
        return code, int(float(t) * 1000)
    except Exception as e:
        return f"ERR {type(e).__name__}", None


def http_code_ms(url: str, timeout: int = 15) -> tuple[str, int | None]:
    """Enako kot curl_code_ms, ampak s stdlib urllib (za pod-mode, brez curl-a)."""
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sola-cluster-report/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return str(r.status), int((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return str(e.code), int((time.monotonic() - t0) * 1000)
    except Exception as e:
        return f"ERR {type(e).__name__}", None


# ---- formatiranje ------------------------------------------------------
def uptime_short(u: str) -> str:
    """'1 week, 3 days, 22 hours, 14 minutes' -> '1t 3d' (slovensko)."""
    u = u.replace(",", "")  # dashboard: "1 week, 3 days, ..." — vejice stran
    m = re.search(r"(?:(\d+) weeks?)?\s*(?:(\d+) days?)?\s*(?:(\d+) hours?)?\s*(?:(\d+) minutes?)?", u)
    w, d, h, mi = (int(x) if x else 0 for x in (m.groups() if m else (None, None, None, None)))
    if w:
        return f"{w}t" + (f" {d}d" if d else "")
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {mi}m"
    return f"{mi}m"


def boot_short(last_boot: str) -> str:
    """'2026-10-18 15:33' -> 'boot 18.10.'"""
    try:
        return "boot " + dt.datetime.strptime(last_boot[:10], "%Y-%m-%d").strftime("%d.%m.")
    except Exception:
        return f"boot {last_boot[:10]}"


def age_human(iso: str) -> str:
    """ISO ts -> '8h', '2d', '35m' (od zdaj nazaj)."""
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if t.tzinfo:
            t = t.astimezone().replace(tzinfo=None)
        sec = max(0, int((NOW - t).total_seconds()))
    except Exception:
        return "?"
    d, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d"
    if h:
        return f"{h}h{m:02d}m" if m else f"{h}h"
    return f"{m}m"


def short_pod(name: str) -> str:
    """Odstrani k8s hash-e iz imena poda: sola-app-66f8c9d89b-abcde -> sola-app.
    Logika: hash segment = dolg >=5 in (vsebuje števko ALI je sam 'hash'-podobno
    mešano). Ne pobriše številk (sola-db-1 ostane) in ne imen brez hash-a."""
    parts = name.split("-")
    # k8s pod ime: <ime>-<replicaset-hash (10)>-<pod-hash (5)>
    # pod-hash = 5 alfanumeričnih (lahko vse črke! abcde) ali >=5 s števko.
    # replicaset-hash = >=8 alfanumeričnih s števko (npr. 66f8c9d89b, 39d54b3d).
    def pod_hash(seg: str) -> bool:
        if not seg.isalnum():
            return False
        return len(seg) == 5 or (len(seg) >= 5 and any(c.isdigit() for c in seg))
    def rs_hash(seg: str) -> bool:
        return seg.isalnum() and len(seg) >= 8 and any(c.isdigit() for c in seg)
    if len(parts) >= 3 and pod_hash(parts[-1]) and rs_hash(parts[-2]):
        return "-".join(parts[:-2])
    if len(parts) >= 2 and pod_hash(parts[-1]):
        return "-".join(parts[:-1])
    return name


def age_sec(s: str) -> int:
    """'8h51m'/'2d'/'35m' -> sekunde (za min/max starosti)."""
    m = re.match(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?", s)
    if not m or not any(m.groups()):
        return 0
    d, h, mi = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60


def pct(v: object) -> str:
    try:
        return f"{round(float(v))}"  # type: ignore[arg-type]
    except Exception:
        return str(v)


def load1dec(v: str) -> str:
    try:
        return f"{float(v):.1f}"
    except Exception:
        return str(v)


def node_label(host: str) -> str:
    """'vmi3676419 (173.212.229.60)' — hostname z vidnim IP-jem."""
    return f"{host} ({IP_BY_HOST.get(host, '?')})"


# ---- zbiranje — HOST mode ----------------------------------------------
def git_sell_info(repo_root: Path) -> dict:
    """Stanje PRIVATnega sell repoa iz LOKALNEGA gita (javni GH API je 404
    brez tokena — zato git, ne API)."""
    try:
        sh(["git", "fetch", ORIGIN, "main", "--quiet"], cwd=repo_root, timeout=60)
        line = sh(["git", "log", "-1", "--format=%H|%cI|%s", "origin/main"],
                  cwd=repo_root).strip()
        sha, iso, msg = line.split("|", 2)
        branch = sh(["git", "branch", "--show-current"], cwd=repo_root).strip()
        st = sh(["git", "status", "-sb"], cwd=repo_root).splitlines()[0].strip()
        return {"sha": sha[:7], "date": iso[:16].replace("T", " "), "msg": msg[:70],
                "branch": branch, "status": st}
    except Exception as e:
        return {"err": f"{type(e).__name__}: {str(e)[:120]}"}


def collect_host(repo_root: Path) -> dict:
    data: dict = {"nodes": {}, "ready": {}, "app": {}, "gh": {}, "cf": {},
                  "web": {}, "per_node": {}, "warnings": []}

    # 1) dashboard health per node + mapiranje ID-jev iz inventoryja
    inv = _dash_req("/api/nodes", timeout=20)
    nodes_list = inv if isinstance(inv, list) else inv.get("nodes", [])
    id_by_name = {n["name"]: n["id"] for n in nodes_list if "id" in n}
    for dash_name, ip, host in NODES:
        rec: dict = {"ip": ip, "host": host, "ok": False}
        try:
            h = dash_health(id_by_name[dash_name])
            m = h.get("monitor") or {}
            rec.update({
                "ok": bool(m.get("ok")),
                "cpu": pct(m.get("cpu_pct")),
                "l1": load1dec(m.get("load1") or "0"),
                "l5": load1dec(m.get("load5") or "0"),
                "l15": load1dec(m.get("load15") or "0"),
                "ram": f"{m.get('mem_used_gb')}/{m.get('mem_total_gb')} GB ({pct(m.get('mem_used_pct'))} %)",
                "disk": pct(m.get("disk_root_pct")),
                "uptime": uptime_short(m.get("uptime") or ""),
                "boot": boot_short(m.get("last_boot") or ""),
                "failed": m.get("failed_units"),
                "k3s": (m.get("k3s") or "").split()[0],   # 'active inactive' -> 'active'
                "err": m.get("error"),
            })
        except Exception as e:
            rec["err"] = f"{type(e).__name__}: {str(e)[:150]}"
            data["warnings"].append(f"{dash_name}: dashboard health FAIL ({rec['err']})")
        data["nodes"][dash_name] = rec

    # 2) kubectl: node Ready/v1 + VSI podi po nodih + app + jobs + longhorn + cloudflared
    pods: list[dict] = []
    try:
        nodes_json = json.loads(kubectl("get nodes -o json"))
        for it in nodes_json["items"]:
            host = it["metadata"]["name"]
            ready = any(c["type"] == "Ready" and c["status"] == "True"
                        for c in it["status"]["conditions"])
            data["ready"][host] = ready
            data.setdefault("k3s_ver", it["status"]["nodeInfo"]["kubeletVersion"])
    except Exception as e:
        data["warnings"].append(f"kubectl get nodes: {type(e).__name__}: {str(e)[:120]}")

    try:
        pods = json.loads(kubectl("get pods -A -o json"))["items"]
        app_pods = [p for p in pods if p["metadata"]["namespace"] == "sola-app"
                    and p["metadata"]["name"].startswith("sola-app-")]
        db_pods = [p for p in pods if p["metadata"]["namespace"] == "sola-app"
                   and p["metadata"]["name"].startswith("sola-db-")]
        for p in pods:
            nn = p["spec"].get("nodeName")
            if not nn:
                continue
            name = short_pod(p["metadata"]["name"])
            age = age_human(p["metadata"]["creationTimestamp"])
            phase = p["status"].get("phase", "?")
            data["per_node"].setdefault(nn, []).append(f"`{name}` {phase} ({age})")
        data["app"]["app_pods"] = len([p for p in app_pods
                                       if p["status"].get("phase") == "Running"])
        data["app"]["app_total"] = len(app_pods)
        data["app"]["app_nodes"] = sorted({p["spec"].get("nodeName", "?")
                                           for p in app_pods})
        data["app"]["app_age"] = sorted(age_human(p["metadata"]["creationTimestamp"])
                                        for p in app_pods) or None
        if db_pods:
            db = db_pods[0]
            data["app"]["db_phase"] = db["status"].get("phase", "?")
            data["app"]["db_age"] = age_human(db["metadata"]["creationTimestamp"])
        else:
            data["app"]["db_phase"] = "MISSING"
    except Exception as e:
        data["warnings"].append(f"kubectl podi: {type(e).__name__}: {str(e)[:120]}")

    try:
        jobs = json.loads(kubectl("get jobs -n sola-app -o json"))["items"]
        done = [j for j in jobs if j["status"].get("succeeded")]
        if done:
            last = sorted(done, key=lambda j: j["status"].get("completionTime", ""))[-1]
            data["app"]["backup"] = {
                "name": last["metadata"]["name"],
                "age": age_human(last["status"].get("completionTime", "")),
                "dur_s": last["status"].get("duration"),
            }
        else:
            data["app"]["backup"] = {"name": "—", "age": "noben Completed", "dur_s": None}
            data["warnings"].append("backup CronJob: noben zadnji job ni Completed")
    except Exception as e:
        data["warnings"].append(f"kubectl jobs: {type(e).__name__}: {str(e)[:120]}")

    try:
        lh_pods = [p for p in pods if p["metadata"]["namespace"] == "longhorn-system"]
        lh = {"engine": 0, "im": 0, "csi": 0}
        for p in lh_pods:
            n = p["metadata"]["name"]
            if p["status"].get("phase") == "Running":
                if n.startswith("engine-image"):
                    lh["engine"] += 1
                elif n.startswith("instance-manager"):
                    lh["im"] += 1
                elif n.startswith("csi-"):
                    lh["csi"] += 1
        data["app"]["longhorn"] = lh
        try:
            vols = json.loads(kubectl("get volumes.longhorn.io -n longhorn-system -o json"))["items"]
            deg = [v["metadata"]["name"] for v in vols
                   if v.get("status", {}).get("robustness") not in (None, "healthy", "Healthy")]
            data["app"]["lh_degraded"] = deg
            if deg:
                data["warnings"].append(f"Longhorn degradirani volumni: {deg}")
        except Exception:
            data["app"]["lh_degraded"] = []
    except Exception as e:
        data["warnings"].append(f"kubectl longhorn: {type(e).__name__}: {str(e)[:120]}")

    try:
        cf_deploy = json.loads(kubectl("get deploy cloudflared -n cloudflared -o json"))
        data["cf"]["ready"] = cf_deploy["status"].get("readyReplicas", 0)
        data["cf"]["replicas"] = cf_deploy["spec"]["replicas"]
        data["cf"]["image"] = cf_deploy["spec"]["template"]["spec"]["containers"][0]["image"].split("/")[-1]
        cf_pods = [p for p in pods if p["metadata"]["namespace"] == "cloudflared"]
        data["cf"]["nodes"] = sorted({p["spec"].get("nodeName", "?") for p in cf_pods})
        logs = kubectl("logs deploy/cloudflared -n cloudflared --tail=300")
        data["cf"]["reg"] = logs.count("Registered tunnel connection")
        errs = re.findall(r"Unauthorized|Tunnel not found|fatal|panic", logs)
        data["cf"]["errs"] = errs[:5]
    except Exception as e:
        data["warnings"].append(f"kubectl cloudflared: {type(e).__name__}: {str(e)[:120]}")

    # 3) git — PRIVAT sell repo iz lokalnega gita
    data["gh"] = git_sell_info(repo_root)

    # 4) e2e curl
    data["web"] = {
        "cf": curl_code_ms("https://reservationapp.site/health"),
        "direct": curl_code_ms(f"http://{NODES[0][1]}:8002/health"),
        "ostc": curl_code_ms("https://ostc-app.org/"),
    }
    return data


# ---- zbiranje — POD mode (gumb v app-u) --------------------------------
# Node metrike beremo DIREKTNO iz node-exporterja (:9100) na vsakem nodu —
# pod v clusterju ne doseže Prometheusa (self-host docker :9090), doseže pa
# node-exporterje; to je isti vir kot scripts/node_report.py. Parser copy
# zraven, da pod-mode NI odvisen od node_report.py v sliki (živa slika teče
# iz veje govorilne, kjer node_report.py ni nujno prisoten).

def _ne_fetch(ip: str) -> tuple[str | None, str]:
    """Vrne (raw /metrics text | None, up-status)."""
    url = f"http://{ip}:9100/metrics"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sola-cluster-report/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            if r.status != 200:
                return None, f"DOWN (HTTP {r.status})"
            return r.read().decode("utf-8", "replace"), "UP"
    except Exception as e:  # timeout, reset, DNS...
        return None, f"DOWN ({type(e).__name__[:12]})"


def _ne_gauge(metrics: str, name: str, **labels) -> float | None:
    """Poišče `name{...} val` ALI `name val` (brez labels) kjer se ujemajo
    dani labels — node_exporter nima `{}` pri node_load*/node_memory_*."""
    for line in metrics.splitlines():
        line = line.strip()
        if not (line.startswith(name + "{") or line.startswith(name + " ")):
            continue
        if line.startswith(name + "{"):
            brace = line.index("{")
            end = line.index("}", brace)
            label_block = line[brace + 1:end]
            val_raw = line[end + 1:].strip()
        else:
            label_block = ""
            val_raw = line[len(name):].strip()
        try:
            val = float(val_raw.split()[0])
        except (ValueError, IndexError):
            continue
        if not labels:
            return val if label_block == "" else None
        parsed = {}
        for kv in label_block.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parsed[k] = v.strip('"')
        if all(parsed.get(k) == v for k, v in labels.items()):
            return val
    return None


def _pod_k8s():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception as exc:
        return (None, None, None, None), f"in-cluster config: {exc}"
    return (client.CoreV1Api(), client.AppsV1Api(),
            client.BatchV1Api(), client.CustomObjectsApi()), None


def _pod_node_metrics(ip: str) -> dict:
    """node-exporter :9100 direktno (pod ne doseže Prometheusa, doseže pa
    node-exporterje — enak vir kot node_report.py)."""
    text, up = _ne_fetch(ip)
    if text is None:
        return {"cpu": "?", "l1": "?", "l5": "?", "l15": "?",
                "ram": "?", "disk": "?", "uptime": "?", "boot": "", "ok": False}
    load1 = _ne_gauge(text, "node_load1")
    load5 = _ne_gauge(text, "node_load5")
    load15 = _ne_gauge(text, "node_load15")
    total = _ne_gauge(text, "node_memory_MemTotal_bytes")
    avail = _ne_gauge(text, "node_memory_MemAvailable_bytes")
    ram_pct = None
    if total and avail is not None:
        ram_pct = round((total - avail) / total * 100)
    disk = None
    for mp in ["/"]:
        size = _ne_gauge(text, "node_filesystem_size_bytes", mountpoint=mp)
        f_avail = _ne_gauge(text, "node_filesystem_avail_bytes", mountpoint=mp)
        if size and f_avail is not None:
            disk = round((size - f_avail) / size * 100)
            break
    boot = _ne_gauge(text, "node_boot_time_seconds")
    up_days = None
    if boot:
        up_days = max(0, int((NOW.timestamp() - boot) / 86400))
    return {
        "cpu": "n/a",  # delta-counter za CPU % ni iz enega vzorca
        "l1": f"{load1:.1f}" if load1 is not None else "?",
        "l5": f"{load5:.1f}" if load5 is not None else "?",
        "l15": f"{load15:.1f}" if load15 is not None else "?",
        "ram": pct(ram_pct) if ram_pct is not None else "?",
        "disk": pct(disk) if disk is not None else "?",
        "uptime": f"{up_days}d" if up_days is not None else "?",
        "boot": f"boot pred {up_days}d" if up_days is not None else "",
        "ok": True,
    }


def collect_pod() -> dict:
    data: dict = {"nodes": {}, "ready": {}, "app": {}, "gh": {}, "cf": {},
                  "web": {}, "per_node": {}, "warnings": []}
    try:
        (core, apps, batch, cust), err = _pod_k8s()
    except Exception as exc:
        data["warnings"].append(f"k8s init: {type(exc).__name__}: {exc}")
        return data
    if err:
        data["warnings"].append(f"k8s init: {err}")
        return data

    ip_by_host = {}
    try:
        nodes = core.list_node().items
        for n in nodes:
            name = n.metadata.name
            ip = next((a.address for a in (n.status.addresses or [])
                       if a.type == "InternalIP"), "")
            ip_by_host[name] = ip
            ready = any(c.type == "Ready" and c.status == "True"
                        for c in (n.status.conditions or []))
            data["ready"][name] = ready
            ni = getattr(n.status, "node_info", None)
            if ni is not None:
                data.setdefault("k3s_ver", getattr(ni, "kubelet_version", None))
    except Exception as e:
        data["warnings"].append(f"k8s nodes: {type(e).__name__}: {str(e)[:120]}")

    for dash_name, ip, host in NODES:
        m = _pod_node_metrics(ip)
        rec = {"ip": ip, "host": host, "ok": m["ok"], "cpu": m["cpu"],
               "l1": m["l1"], "l5": m["l5"], "l15": m["l15"], "ram": m["ram"],
               "disk": m["disk"], "uptime": m["uptime"], "boot": m["boot"],
               "failed": "n/a", "k3s": "k8s", "err": None}
        data["nodes"][dash_name] = rec
    if ip_by_host:
        extra = set(ip_by_host) - {h for _, _, h in NODES}
        for h in extra:
            data["ready"][h] = data["ready"].get(h, False)

    items: list[dict] = []
    try:
        pods = core.list_pod_for_all_namespaces().items
        for p in pods:
            dd = p.to_dict()
            dd.setdefault("status", {}).setdefault("phase", "?")
            items.append(dd)
        app_pods = [d for d in items if d["metadata"]["namespace"] == "sola-app"
                    and d["metadata"]["name"].startswith("sola-app-")]
        db_pods = [d for d in items if d["metadata"]["namespace"] == "sola-app"
                   and d["metadata"]["name"].startswith("sola-db-")]
        for d in items:
            nn = d["spec"].get("node_name") or d["spec"].get("nodeName")
            if not nn:
                continue
            name = short_pod(d["metadata"]["name"])
            created = d["metadata"].get("creation_timestamp") or d["metadata"].get("creationTimestamp")
            age = age_human(str(created))
            phase = d["status"].get("phase", "?")
            data["per_node"].setdefault(nn, []).append(f"`{name}` {phase} ({age})")
        data["app"]["app_pods"] = len([d for d in app_pods
                                       if d["status"].get("phase") == "Running"])
        data["app"]["app_total"] = len(app_pods)
        data["app"]["app_nodes"] = sorted({d["spec"].get("node_name") or d["spec"].get("nodeName", "?")
                                           for d in app_pods})
        data["app"]["app_age"] = sorted(age_human(str(d["metadata"].get("creation_timestamp")
                                                     or d["metadata"].get("creationTimestamp")))
                                        for d in app_pods) or None
        if db_pods:
            db = db_pods[0]
            data["app"]["db_phase"] = db["status"].get("phase", "?")
            data["app"]["db_age"] = age_human(str(db["metadata"].get("creation_timestamp")
                                                  or db["metadata"].get("creationTimestamp")))
        else:
            data["app"]["db_phase"] = "MISSING"

        lh = {"engine": 0, "im": 0, "csi": 0}
        for d in items:
            if d["metadata"]["namespace"] != "longhorn-system":
                continue
            n = d["metadata"]["name"]
            if d["status"].get("phase") == "Running":
                if n.startswith("engine-image"):
                    lh["engine"] += 1
                elif n.startswith("instance-manager"):
                    lh["im"] += 1
                elif n.startswith("csi-"):
                    lh["csi"] += 1
        data["app"]["longhorn"] = lh
        try:
            vols = cust.list_namespaced_custom_object("longhorn.io", "v1beta1",
                                                      "longhorn-system", "volumes")
            deg = [v["metadata"]["name"] for v in vols.get("items", [])
                   if v.get("status", {}).get("robustness") not in (None, "healthy", "Healthy")]
            data["app"]["lh_degraded"] = deg
        except Exception:
            try:
                vols = cust.list_namespaced_custom_object("longhorn.io", "v1beta2",
                                                          "longhorn-system", "volumes")
                deg = [v["metadata"]["name"] for v in vols.get("items", [])
                       if v.get("status", {}).get("robustness") not in (None, "healthy", "Healthy")]
                data["app"]["lh_degraded"] = deg
            except Exception:
                data["app"]["lh_degraded"] = []
    except Exception as e:
        data["warnings"].append(f"k8s podi: {type(e).__name__}: {str(e)[:120]}")

    try:
        jobs = batch.list_namespaced_job("sola-app").items
        done = [j for j in jobs if getattr(j.status, "succeeded", 0)]
        if done:
            last = sorted(done, key=lambda j: str(getattr(j.status, "completion_time", "") or ""))[-1]
            data["app"]["backup"] = {
                "name": last.metadata.name,
                "age": age_human(str(getattr(last.status, "completion_time", "") or "")),
                "dur_s": getattr(last.status, "duration", None),
            }
        else:
            data["app"]["backup"] = {"name": "—", "age": "noben Completed", "dur_s": None}
    except Exception as e:
        data["warnings"].append(f"k8s jobs: {type(e).__name__}: {str(e)[:120]}")

    try:
        cf_deploy = apps.read_namespaced_deployment("cloudflared", "cloudflared")
        data["cf"]["ready"] = getattr(cf_deploy.status, "ready_replicas", 0) or 0
        data["cf"]["replicas"] = cf_deploy.spec.replicas
        data["cf"]["image"] = cf_deploy.spec.template.spec.containers[0].image.split("/")[-1]
        data["cf"]["nodes"] = sorted({d["spec"].get("node_name") or d["spec"].get("nodeName", "?")
                                      for d in items if d["metadata"]["namespace"] == "cloudflared"})
        data["cf"]["reg"] = None  # pod nima RBAC za logs — preskočeno
    except Exception as e:
        data["warnings"].append(f"k8s cloudflared: {type(e).__name__}: {str(e)[:120]}")

    # GH (sell) prek API s tokenom — za gumb; brez tokena samo opomba
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        try:
            req = urllib.request.Request(GH_API, headers={
                "Authorization": "Bearer " + tok,
                "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                repo = json.loads(r.read().decode())
            branch = repo.get("default_branch", "main")
            req = urllib.request.Request(GH_API + f"/commits/{branch}", headers={
                "Authorization": "Bearer " + tok,
                "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                cm = json.loads(r.read().decode())
            data["gh"] = {
                "sha": cm["sha"][:7],
                "date": cm["commit"]["committer"]["date"][:16].replace("T", " "),
                "msg": cm["commit"]["message"].splitlines()[0][:70],
                "branch": branch,
                "status": f"push prek gumba ({time.strftime('%H:%M')})",
            }
        except Exception as e:
            data["gh"] = {"err": f"{type(e).__name__}: {str(e)[:120]}"}
    else:
        data["gh"] = {"err": "GITHUB_TOKEN ni nastavljen (secret sola-secrets)"}

    data["web"] = {
        "cf": http_code_ms("https://reservationapp.site/health"),
        "direct": http_code_ms(f"http://{NODES[0][1]}:8002/health"),
        "ostc": http_code_ms("https://ostc-app.org/"),
    }
    return data


# ---- render ------------------------------------------------------------
def render(d: dict) -> str:
    L: list[str] = []
    A = L.append
    A(f"## 📋 Poročilo — {NOW.strftime('%d.%m.%Y')} ~{NOW.strftime('%H:%M')}")
    A("")

    # nodi
    k3s_ver = d.get("k3s_ver", "?")
    ready_all = all(d["ready"].get(host) for _, _, host in NODES)
    status_txt = "vsi ✅ Ready (control-plane,etcd)" if ready_all else "⚠️ nekdo ni Ready!"
    A(f"### 🖥️ Trije nodi (k3s HA, {k3s_ver}) — {status_txt}")
    A("")
    A("| | **node1** (sola-node1) | **node2** | **node3** |")
    A("|---|---|---|---|")
    dash1, dash2, dash3 = (d["nodes"][n] for n, _, _ in NODES)
    rows = [
        ("IP / host", [f"{r['ip']} / {r['host']}" for r in (dash1, dash2, dash3)]),
        ("CPU", [f"{r['cpu']} % (load {r['l1']}/{r['l5']}/{r['l15']})" if r["cpu"] != "n/a"
                else f"load {r['l1']}/{r['l5']}/{r['l15']}" for r in (dash1, dash2, dash3)]),
        ("RAM", [r["ram"] for r in (dash1, dash2, dash3)]),
        ("Disk `/`", [f"{r['disk']} %" for r in (dash1, dash2, dash3)]),
        ("Uptime", [f"{r['uptime']} ({r['boot']})" for r in (dash1, dash2, dash3)]),
        ("systemd failed", [str(r["failed"]) for r in (dash1, dash2, dash3)]),
        ("k3s", [f"{r['k3s']} ✅" if r["ok"] else f"{r['k3s']} ⚠️" for r in (dash1, dash2, dash3)]),
    ]
    for label, cells in rows:
        A(f"| {label} | " + " | ".join(cells) + " |")
    A("")
    if any(not r["ok"] or r.get("err") for r in (dash1, dash2, dash3)):
        for r in (dash1, dash2, dash3):
            if not r["ok"] or r.get("err"):
                A(f"- ⚠️ {r['host']} ({r['ip']}): {r.get('err') or 'monitor OK=false'}")
        A("")

    # kaj teče na katerem nodu — z IP-ji in starostjo podov
    per_node = d.get("per_node", {})
    A("### 📍 Kaj teče na katerem nodu (podi + starost)")
    A("")
    for dash_name, ip, host in NODES:
        pods = sorted(per_node.get(host, []))
        if not pods:
            A(f"**{dash_name} — {host} (`{ip}`)**: ni podov/zagon še ni znan.")
            continue
        # združi ponovitve istega poda: `sola-app` Running (2h) ×3 → `sola-app` Running (3×, 2h)
        by_name: dict[str, list[str]] = {}
        for p in pods:
            base, _, rest = p.partition(" (")
            by_name.setdefault(base, []).append(rest.rstrip(")"))
        parts = []
        for base, ages in sorted(by_name.items()):
            if len(ages) > 1:
                los, his = min(ages, key=age_sec), max(ages, key=age_sec)
                rng = los if los == his else f"{los}–{his}"
                parts.append(f"{base} ({len(ages)}×, {rng})")
            else:
                parts.append(f"{base} ({ages[0]})")
        A(f"**{dash_name} — {host} (`{ip}`)**: " + " · ".join(parts) + ".")
    A("")

    # app
    A("### 📦 App (sola-app / reservationapp.site)")
    A("")
    app = d.get("app", {})
    if app.get("app_pods") is not None:
        age_txt = ""
        if app.get("app_age"):
            ages = app["app_age"]
            age_txt = f", starost {ages[0]}–{ages[-1]}"
        podi_txt = ", ".join(node_label(n) for n in (app.get("app_nodes") or ["?"]))
        A(f"- **sola-app: {app['app_pods']}/{app.get('app_total') or 3} Running**{age_txt}"
          f" — podi na: {podi_txt}.")
    A(f"- **sola-db-1: {app.get('db_phase')}**" +
      (f" ({app.get('db_age')})" if app.get("db_age") else "") + ".")
    bk = app.get("backup")
    if bk:
        dur = bk.get("dur_s")
        A(f"- **Backup CronJob: zadnji Completed pred {bk['age']}**"
          + (f" ({bk['name']}, trajanje {dur}s)" if dur else "") + ".")
    direct_code, direct_ms = d.get("web", {}).get("direct", ("ERR", None))
    ms_txt = f" ({direct_ms} ms)" if direct_ms is not None else ""
    A(f"- Health: `/health` direktno na {NODES[0][1]}:8002 → **{direct_code}**{ms_txt}.")
    lh = app.get("longhorn")
    if lh:
        deg = app.get("lh_degraded") or []
        A(f"- Longhorn: engine-image {lh['engine']}/3, instance-manager {lh['im']}/3, "
          f"csi {lh['csi']} Running (4×3)", )
        if deg:
            A(f"  ⚠️ degradirani volumni: {deg}")
    A("")

    # github — PRIVAT sell repo
    A(f"### 🐙 GitHub — {GH_REPO} (privat)")
    A("")
    gh = d.get("gh", {})
    if gh.get("sha"):
        A(f"- Zadnji commit na `origin/main`: `{gh['sha']}` ({gh.get('date', '')}) — "
          + f"*{gh.get('msg', '')}*")
        if gh.get("branch"):
            A(f"- Lokalna veja `{gh['branch']}`: `{gh['status']}`.")
        A("- To poročilo živi v `reports/` tega repoa "
          "(`latest.md` + timestamp kopija) — beri ga tu, kjerkoli si.")
    elif gh.get("err"):
        A(f"- ⚠️ {gh['err']}")
    A("")

    # cloudflare
    A("### ☁️ Cloudflare tunnel")
    A("")
    cf = d.get("cf", {})
    if cf.get("replicas"):
        A(f"- **Deployment {cf.get('ready')}/{cf.get('replicas')} Running**"
          + (f" (slika `{cf.get('image')}`)" if cf.get("image") else "")
          + (", 1 pod na vsakem nodu." if len(cf.get("nodes", [])) == 3 else "."))
    if cf.get("reg") is not None:
        err_txt = f", {len(cf.get('errs', []))} napak" if cf.get("errs") else " — 0 napak"
        A(f"- Logi: **{cf['reg']}× `Registered tunnel connection`**{err_txt}.")
    cf_code, cf_ms = d.get("web", {}).get("cf", ("ERR", None))
    ostc_code, _ = d.get("web", {}).get("ostc", ("ERR", None))
    ms_txt = f" ({cf_ms} ms)" if cf_ms is not None else ""
    A(f"- End-to-end: `https://reservationapp.site/health` → **{cf_code}**{ms_txt} "
      f"· `https://ostc-app.org/` → {ostc_code} (star app — znano).")
    A("")

    # sklep
    warns = d.get("warnings", [])
    if warns:
        A(f"**Sklep: ⚠️ {len(warns)} opozoril.**")
        for w in warns:
            A(f"- {w}")
    else:
        A("**Sklep: vse zeleno.** Trije nodi zdravi, app + baza + backupi OK, "
          "tunel povezan in javno odziven.")
    return "\n".join(L) + "\n"


# ---- push: HOST (git worktree na origin) -------------------------------
def git_push(files: list[Path], commit_msg: str, repo_root: Path) -> None:
    """Commit samo navedenih datotek na origin/main + push, brez dotikanja
    uporabnikove delovne kopije (temp worktree iz origin/main)."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    branch = f"_report/{ts}"
    tmp = Path(tempfile.mkdtemp(prefix="sola-report-"))
    try:
        sh(["git", "fetch", ORIGIN, "main", "--quiet"], cwd=repo_root)
        sh(["git", "worktree", "add", "-b", branch, str(tmp), f"{ORIGIN}/main"],
           cwd=repo_root)
        for f in files:
            rel = f.relative_to(repo_root)
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        rels = [str(f.relative_to(repo_root)) for f in files]
        sh(["git", "add", *rels], cwd=tmp)
        sh(["git", "-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_MAIL}",
            "commit", "-m", commit_msg], cwd=tmp)
        sh(["git", "push", ORIGIN, "HEAD:main"], cwd=tmp, timeout=120)
    finally:
        sh(["git", "worktree", "remove", "--force", str(tmp)], cwd=repo_root)
        try:
            sh(["git", "branch", "-D", branch], cwd=repo_root)
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


# ---- push: POD (GH Contents API s tokenom) ------------------------------
def gh_push_contents(body: str, ts: str) -> tuple[bool, str]:
    """Naloži reports/latest.md + timestamp .md na privat sell prek GH
    Contents API. Token = env GITHUB_TOKEN (secret sola-secrets)."""
    tok = os.environ.get("GITHUB_TOKEN", "")
    if not tok:
        return False, "GITHUB_TOKEN ni nastavljen (secret sola-secrets) — ne morem naložiti na GitHub."
    headers = {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    for path, content in [("reports/latest.md", body),
                          (f"reports/{ts}.md", body)]:
        sha = None
        try:
            req = urllib.request.Request(GH_API + f"/contents/{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                sha = json.loads(r.read().decode()).get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return False, f"GET {path}: HTTP {e.code}"
        payload = {
            "message": f"📋 Status report — {ts} (gumb)",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(
            GH_API + f"/contents/{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return False, f"PUT {path}: HTTP {e.code} — {e.read()[:200]!r}"
    return True, f"{GH_BLOB}/reports/latest.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Celovit status report k3s clustra → markdown → GitHub (privat sell)")
    ap.add_argument("--no-push", action="store_true", help="samo zgeneriraj + shrani, ne pushaj")
    ap.add_argument("--out", default="reports", help="izhodna mapa (default: reports/)")
    ap.add_argument("--mode", choices=["host", "pod"], default="host",
                    help="host = dashboard+SSH (mašina), pod = in-cluster (gumb)")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = NOW.strftime("%Y%m%d-%H%M%S")
    dated = out_dir / f"{ts}.md"          # timestamp ime, edinstveno per run
    latest = out_dir / "latest.md"

    if args.mode == "pod":
        d = collect_pod()
        body = render(d)
        dated.write_text(body)
        latest.write_text(body)
        print(body)
        print(f"\n— shranjeno: {dated} + {latest} (mode=pod)")
        if not args.no_push:
            ok, msg = gh_push_contents(body, ts)
            print(("✅ " if ok else "❌ ") + msg)
            return 0 if ok else 1
        return 0

    d = collect_host(repo_root)
    body = render(d)
    dated.write_text(body)
    latest.write_text(body)
    print(body)
    print(f"\n— shranjeno: {dated} + {latest}")

    if not args.no_push:
        try:
            # push: report + skripta + njeni testi (da vse pride v repo)
            test_file = repo_root / "tests" / "test_cluster_report.py"
            to_push = [dated, latest, Path(__file__).resolve()]
            if test_file.exists():
                to_push.append(test_file)
            git_push(to_push,
                     f"📋 Status report — {NOW.strftime('%d.%m.%Y %H:%M')}",
                     repo_root)
            print(f"✅ pushano na {ORIGIN}/main → {GH_BLOB}/{latest.relative_to(repo_root)}")
        except Exception as e:
            print(f"❌ PUSH FAIL: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
