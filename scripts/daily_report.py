"""Daily k3s/Longhorn health report.

Runs as a Kubernetes CronJob and sends a read-only cluster health report by email.
The report is intentionally split into small "agent-style" collectors so the same
structure can later be reused by the Pi 3 Hermes agent.

Usage:
  python -m scripts.daily_report
"""

import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.routers.blocked_dates import _send_email

try:
    from kubernetes import client, config
except ImportError:  # pragma: no cover - exercised inside the container image
    client = None
    config = None


LONGHORN_VERSIONS = ("v1beta2", "v1beta1")
LONGHORN_NAMESPACE = "longhorn-system"


def now_ljubljana() -> datetime:
    return datetime.now(ZoneInfo("Europe/Ljubljana"))


def fmt_dt(value) -> str:
    if not value:
        return "unknown"
    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(value)


def fmt_age(value) -> str:
    if not value:
        return "unknown"
    try:
        age = datetime.now(timezone.utc) - value
        days = max(age.days, 0)
        if days >= 365:
            return f"{days // 365}y {days % 365}d"
        return f"{days}d"
    except Exception:
        return "unknown"


def load_kube():
    if client is None or config is None:
        return None, None, "Python package 'kubernetes' is not installed"
    try:
        if os.getenv("KUBECONFIG"):
            config.load_kube_config()
        else:
            config.load_incluster_config()
        core = client.CoreV1Api()
        apps = client.AppsV1Api()
        batch = client.BatchV1Api()
        custom = client.CustomObjectsApi()
        return (core, apps, batch, custom), None, None
    except Exception as exc:
        return None, None, f"Kubernetes API unavailable: {type(exc).__name__}: {exc}"


def safe_list(func, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        return list(getattr(result, "items", []) or []), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def get_dict_path(data, path, default=None):
    current = data
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return default
    return current


def condition_map(obj) -> dict:
    conditions = get_dict_path(obj, ["status", "conditions"], []) or []
    result = {}
    for condition in conditions:
        ctype = getattr(condition, "type", None)
        if ctype is None and isinstance(condition, dict):
            ctype = condition.get("type")
        if ctype:
            result[ctype] = condition
    return result


def condition_status(obj, ctype: str) -> str:
    condition = condition_map(obj).get(ctype, {})
    status = getattr(condition, "status", None)
    if status is None and isinstance(condition, dict):
        status = condition.get("status")
    return str(status or "Unknown")


def pod_restart_count(pod) -> int:
    total = 0
    statuses = getattr(getattr(pod, "status", None), "container_statuses", None) or []
    init_statuses = getattr(getattr(pod, "status", None), "init_container_statuses", None) or []
    for status in list(statuses) + list(init_statuses):
        total += int(getattr(status, "restart_count", 0) or 0)
    return total


def collect_k3s_agent(core, apps, batch):
    nodes, nodes_err = safe_list(core.list_node)
    pods, pods_err = safe_list(core.list_pod_for_all_namespaces)
    events, events_err = safe_list(core.list_event_for_all_namespaces, limit=300)
    services, services_err = safe_list(core.list_service_for_all_namespaces)
    pvcs, pvcs_err = safe_list(core.list_persistent_volume_claim_for_all_namespaces)
    deployments, deployments_err = safe_list(apps.list_deployment_for_all_namespaces)
    statefulsets, statefulsets_err = safe_list(apps.list_stateful_set_for_all_namespaces)
    daemonsets, daemonsets_err = safe_list(apps.list_daemon_set_for_all_namespaces)
    jobs, jobs_err = safe_list(batch.list_job_for_all_namespaces)
    cronjobs, cronjobs_err = safe_list(batch.list_cron_job_for_all_namespaces)

    pod_phase_counts = Counter(getattr(pod.status, "phase", "Unknown") for pod in pods)
    total_restarts = sum(pod_restart_count(pod) for pod in pods)
    failed_jobs = [job for job in jobs if int(getattr(job.status, "failed", 0) or 0) > 0]
    active_jobs = [job for job in jobs if job.status.active]
    suspended_cronjobs = [cj for cj in cronjobs if cj.spec.suspend]
    active_cronjobs = [cj for cj in cronjobs if getattr(cj.status, "active", [])]

    warning_events = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for event in events:
        event_time = getattr(event, "last_timestamp", None) or getattr(event, "event_time", None)
        if getattr(event, "type", "") == "Warning" and event_time and event_time.replace(tzinfo=timezone.utc) >= cutoff:
            warning_events.append(event)

    return {
        "nodes": nodes,
        "pods": pods,
        "events": events,
        "services": services,
        "pvcs": pvcs,
        "deployments": deployments,
        "statefulsets": statefulsets,
        "daemonsets": daemonsets,
        "jobs": jobs,
        "cronjobs": cronjobs,
        "errors": {
            "nodes": nodes_err,
            "pods": pods_err,
            "events": events_err,
            "services": services_err,
            "pvcs": pvcs_err,
            "deployments": deployments_err,
            "statefulsets": statefulsets_err,
            "daemonsets": daemonsets_err,
            "jobs": jobs_err,
            "cronjobs": cronjobs_err,
        },
        "summary": {
            "pod_phase_counts": pod_phase_counts,
            "total_restarts": total_restarts,
            "failed_jobs": failed_jobs,
            "active_jobs": active_jobs,
            "suspended_cronjobs": suspended_cronjobs,
            "active_cronjobs": active_cronjobs,
            "warning_events": warning_events[:20],
            "warning_event_count": len(warning_events),
        },
    }


def collect_longhorn_agent(custom):
    collected = {}
    errors = {}
    resources = {
        "volumes": "volumes",
        "nodes": "nodes",
        "replicas": "replicas",
        "engines": "engines",
        "backups": "backups",
        "backup_targets": "backuptargets",
    }

    for name, plural in resources.items():
        items = []
        last_error = None
        for version in LONGHORN_VERSIONS:
            try:
                result = custom.list_namespaced_custom_object(
                    "longhorn.io",
                    version,
                    LONGHORN_NAMESPACE,
                    plural,
                )
                items = list(result.get("items", []) or [])
                last_error = None
                break
            except Exception as exc:
                last_error = f"{version}: {type(exc).__name__}: {exc}"
        collected[name] = items
        errors[name] = last_error

    volumes = collected.get("volumes", [])
    volume_robustness = Counter(get_dict_path(v, ["status", "robustness"], "unknown") for v in volumes)
    volume_state = Counter(get_dict_path(v, ["status", "state"], "unknown") for v in volumes)
    degraded = [v for v in volumes if get_dict_path(v, ["status", "robustness"]) in ("degraded", "faulted")]
    rebuilding = [v for v in volumes if get_dict_path(v, ["status", "cloneStatus", "state"]) == "syncing"]

    lh_nodes = collected.get("nodes", [])
    storage_lines = []
    longhorn_node_ready = {}
    for node in lh_nodes:
        name = get_dict_path(node, ["metadata", "name"], "unknown")
        longhorn_node_ready[name] = condition_status(node, "Ready")
        maximum = 0
        available = 0
        disk_status = get_dict_path(node, ["status", "diskStatus"], {}) or {}
        for disk in disk_status.values():
            maximum += int(get_dict_path(disk, ["storageMaximum"], 0) or 0)
            available += int(get_dict_path(disk, ["storageAvailable"], 0) or 0)
        used_pct = None
        if maximum:
            used_pct = round(((maximum - available) / maximum) * 100, 1)
        storage_lines.append((name, used_pct, maximum, available))

    return {
        "items": collected,
        "errors": errors,
        "summary": {
            "volume_robustness": volume_robustness,
            "volume_state": volume_state,
            "degraded_volumes": degraded,
            "rebuilding_volumes": rebuilding,
            "storage_lines": storage_lines,
            "longhorn_node_ready": longhorn_node_ready,
        },
    }


def estimate_node_lifetime(node, k3s_summary, longhorn_summary):
    name = getattr(getattr(node, "metadata", None), "name", "unknown")
    score = 0
    reasons = []

    for pressure in ("DiskPressure", "MemoryPressure", "PIDPressure"):
        if condition_status(node, pressure) == "True":
            score += 60 if pressure == "DiskPressure" else 40
            reasons.append(f"{pressure}=True")

    if condition_status(node, "Ready") != "True":
        score += 100
        reasons.append("Ready != True")

    age = getattr(getattr(node, "metadata", None), "creation_timestamp", None)
    if age:
        try:
            age_days = (datetime.now(timezone.utc) - age).days
            if age_days > 365:
                score += 10
                reasons.append(f"node age {age_days}d")
        except Exception:
            pass

    restarts_by_node = defaultdict(int)
    for pod in k3s_summary["pods"]:
        if getattr(pod.spec, "node_name", None) == name:
            restarts_by_node[name] += pod_restart_count(pod)
    node_restarts = restarts_by_node.get(name, 0)
    if node_restarts >= 20:
        score += 25
        reasons.append(f"pod restarts {node_restarts}")
    elif node_restarts >= 10:
        score += 15
        reasons.append(f"pod restarts {node_restarts}")

    storage_pct = None
    for lh_name, pct, _maximum, _available in longhorn_summary["summary"]["storage_lines"]:
        if lh_name == name:
            storage_pct = pct
            break
    if storage_pct is not None:
        if storage_pct >= 90:
            score += 40
            reasons.append(f"Longhorn disk used {storage_pct}%")
        elif storage_pct >= 80:
            score += 20
            reasons.append(f"Longhorn disk used {storage_pct}%")

    for lh_name, ready in longhorn_summary.get("longhorn_node_ready", {}).items():
        if lh_name == name and ready != "True":
            score += 30
            reasons.append(f"Longhorn node ready={ready}")

    failed_jobs = k3s_summary["summary"]["failed_jobs"]
    warning_events = k3s_summary["summary"]["warning_events"]
    node_warning_events = []
    for event in warning_events:
        involved = getattr(event, "involved_object", None)
        involved_name = getattr(involved, "name", "") if involved else ""
        if name in involved_name:
            node_warning_events.append(event)
    if node_warning_events:
        score += min(20, len(node_warning_events) * 5)
        reasons.append(f"recent warning events {len(node_warning_events)}")

    if failed_jobs:
        score += 10
        reasons.append(f"failed jobs {len(failed_jobs)}")

    if score >= 80:
        status = "CRITICAL"
        estimate = "tveganje izpada danes ali v naslednjih nekaj dneh"
    elif score >= 50:
        status = "WARNING"
        estimate = "tveganje v naslednjih dneh do 2 tednih"
    elif score >= 20:
        status = "WATCH"
        estimate = "stabilno, ampak zahteva spremljanje; ocena tedni do meseci"
    else:
        status = "OK"
        estimate = "brez znanih tveganj; ocena mesece, če se trend ne poslabša"

    if not reasons:
        reasons.append("no high-risk signals found")

    return {
        "node": name,
        "score": score,
        "status": status,
        "estimate": estimate,
        "reasons": reasons,
    }


def _get_week_start(d: date) -> date:
    """Vrne ponedeljek tedna za dan d"""
    return d - timedelta(days=d.weekday())


def _get_week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def _check_consecutive_days(dates_list) -> bool:
    """Preveri ali so 3 datumi zaporedni dnevi"""
    if len(dates_list) < 3:
        return False
    sorted_dates = sorted(dates_list)
    for i in range(len(sorted_dates) - 2):
        if (sorted_dates[i+1] - sorted_dates[i]).days == 1 and \
           (sorted_dates[i+2] - sorted_dates[i+1]).days == 1:
            return True
    return False


def collect_app_data_agent():
    """Preveri celovitost podatkov (ocene, rezervacije) za danes + 30 dni.

    Namen: zazna morebitne bug-e, ki so spustili neveljavne podatke mimo validacije.
    """
    from app.database import SessionLocal
    from app.models import Assessment, BlockedDate

    db = SessionLocal()
    try:
        today = date.today()
        end = today + timedelta(days=30)
        issues = []

        # ── Assessments ──
        assessments = db.query(Assessment).filter(
            Assessment.date >= today,
            Assessment.date <= end
        ).order_by(Assessment.razred, Assessment.date).all()

        # Group by class + week
        by_class_week = defaultdict(list)
        for a in assessments:
            ws = _get_week_start(a.date)
            by_class_week[(a.razred, ws)].append(a)

        for (razred_class, ws), group in by_class_week.items():
            we = _get_week_end(ws)
            ws_s = ws.strftime("%d.%m.")
            we_s = we.strftime("%d.%m.%Y")

            # Max 3 per week (any type)
            if len(group) > 3:
                issues.append(
                    f"❌ {razred_class}: {len(group)} ocenjevanj v tednu "
                    f"{ws_s}-{we_s} (dovoljeno max 3)"
                )

            # Max 2 normal (non-ponavljanje) per week
            normal = [a for a in group if not a.ponavljanje]
            if len(normal) > 2:
                issues.append(
                    f"❌ {razred_class}: {len(normal)} običajnih ocenjevanj v tednu "
                    f"{ws_s}-{we_s} (dovoljeno max 2)"
                )

            # Same-day duplicates
            date_counts = Counter(a.date for a in group)
            for d, cnt in date_counts.items():
                if cnt > 1:
                    issues.append(
                        f"❌ {razred_class}: {cnt} ocenjevanj na isti dan {d}"
                    )

            # 3 consecutive days
            all_dates = sorted(set(a.date for a in group))
            if _check_consecutive_days(all_dates):
                issues.append(
                    f"❌ {razred_class}: ocenjevanja na 3 zaporedne dni v tednu "
                    f"{ws_s}-{we_s}"
                )

        # Assessments on blocked dates
        blocked = db.query(BlockedDate).filter(
            BlockedDate.date >= today,
            BlockedDate.date <= end
        ).all()
        blocked_set = {(b.razred, b.date) for b in blocked}

        for a in assessments:
            if (a.razred, a.date) in blocked_set:
                issues.append(
                    f"⚠️ {a.razred} ima ocenjevanje na zaseden datum {a.date}"
                )

        # ── Blocked dates without any assessments (info only) ──
        affected_blocked = 0
        for b in blocked:
            has_assessment = any(
                a.razred == b.razred and a.date == b.date for a in assessments
            )
            if has_assessment:
                affected_blocked += 1

        total_assessments = len(assessments)
        total_blocked = len(blocked)

        return {
            "issues": issues,
            "total_assessments": total_assessments,
            "total_blocked": total_blocked,
            "period_start": today.isoformat(),
            "period_end": end.isoformat(),
        }
    finally:
        db.close()


def render_report(k3s, longhorn, app_data=None, kube_error=None):
    lines = []
    generated = now_ljubljana().strftime("%Y-%m-%d %H:%M %Z")
    lines.append("🛡️ Daily k3s/Longhorn health report")
    lines.append(f"Generated: {generated}")
    lines.append("")

    if kube_error:
        lines.append(f"## Executive summary")
        lines.append(f"Overall: CRITICAL")
        lines.append("")
        lines.append(f"Kubernetes API error: {kube_error}")
        return "\n".join(lines)

    nodes = k3s["nodes"]
    pods = k3s["pods"]
    summary = k3s["summary"]
    long_items = longhorn["items"]
    long_summary = longhorn["summary"]
    long_errors = longhorn["errors"]

    not_ready_nodes = [n for n in nodes if condition_status(n, "Ready") != "True"]
    pressure_nodes = []
    for node in nodes:
        pressure_types = ["MemoryPressure", "DiskPressure", "PIDPressure"]
        if any(condition_status(node, pressure_type) == "True" for pressure_type in pressure_types):
            pressure_nodes.append(node)

    overall = "OK"
    if not_ready_nodes or long_summary["degraded_volumes"]:
        overall = "CRITICAL"
    elif pressure_nodes or summary["failed_jobs"] or summary["warning_event_count"] > 10:
        overall = "WARNING"
    elif summary["total_restarts"] > 10 or long_summary["rebuilding_volumes"]:
        overall = "WATCH"

    lines.append("## Executive summary")
    lines.append(f"Overall: {overall}")
    lines.append(f"Nodes: {len(nodes)} total, {len(not_ready_nodes)} not-ready, {len(pressure_nodes)} with pressure")
    lines.append(f"Pods: {len(pods)} total, phases={dict(summary['pod_phase_counts'])}, restarts={summary['total_restarts']}")
    lines.append(f"Jobs: {len(k3s['jobs'])} total, {len(summary['failed_jobs'])} failed, {len(summary['active_jobs'])} active")
    lines.append(f"CronJobs: {len(k3s['cronjobs'])} total, {len(summary['active_cronjobs'])} active, {len(summary['suspended_cronjobs'])} suspended")
    lines.append(f"Recent warning events: {summary['warning_event_count']}")
    lines.append("")

    lines.append("## k3s agent")
    for node in nodes:
        name = getattr(getattr(node, "metadata", None), "name", "unknown")
        roles = sorted(k for k in getattr(getattr(node, "metadata", None), "labels", {}).keys() if k.startswith("node-role.kubernetes.io/"))
        roles_text = ", ".join(role.replace("node-role.kubernetes.io/", "") for role in roles) if roles else "<none>"
        ready = condition_status(node, "Ready")
        lines.append(f"- {name}: Ready={ready}, roles={roles_text}, age={fmt_age(getattr(getattr(node, 'metadata', None), 'creation_timestamp', None))}")
    if not nodes:
        lines.append("- no nodes returned")
    lines.append("")

    lines.append("## Longhorn agent")
    volume_robustness = dict(long_summary["volume_robustness"])
    volume_state = dict(long_summary["volume_state"])
    lines.append(f"Volumes: {len(long_items.get('volumes', []))} total, robustness={volume_robustness}, state={volume_state}")
    lines.append(f"Degraded/faulted volumes: {len(long_summary['degraded_volumes'])}")
    lines.append(f"Rebuilding volumes: {len(long_summary['rebuilding_volumes'])}")
    for name, pct, maximum, available in long_summary["storage_lines"]:
        max_gb = round(maximum / 1024**3, 1) if maximum else None
        avail_gb = round(available / 1024**3, 1) if available else None
        pct_text = f"{pct}%" if pct is not None else "unknown"
        lh_ready = long_summary.get("longhorn_node_ready", {}).get(name, "unknown")
        lines.append(f"- {name}: LonghornReady={lh_ready}, used={pct_text}, available={avail_gb} GiB / {max_gb} GiB")
    if long_summary["degraded_volumes"]:
        lines.append("Degraded/faulted volume details:")
        for volume in long_summary["degraded_volumes"]:
            vol_name = get_dict_path(volume, ["metadata", "name"], "unknown")
            robustness = get_dict_path(volume, ["status", "robustness"], "unknown")
            state = get_dict_path(volume, ["status", "state"], "unknown")
            lines.append(f"- {vol_name}: robustness={robustness}, state={state}")
    if long_errors.get("volumes"):
        lines.append(f"Longhorn volumes API error: {long_errors['volumes']}")
    lines.append("")

    lines.append("## Node health / lifetime estimate agent")
    estimates = [estimate_node_lifetime(node, k3s, longhorn) for node in nodes]
    for item in estimates:
        lines.append(f"- {item['node']}: {item['status']} score={item['score']} — {item['estimate']}")
        for reason in item["reasons"]:
            lines.append(f"  - {reason}")
    if not estimates:
        lines.append("- no node estimates")
    lines.append("")
    lines.append("Note: lifetime estimate is heuristic, based on readiness, pressure conditions, pod restarts, failed jobs, recent warning events and Longhorn disk usage.")
    lines.append("")
    lines.append("Dokumentacija:")
    lines.append("  https://github.com/os-tc-jesenice/reservation_app/blob/main/documentation/navodila-vodstvo.md")
    lines.append("  https://github.com/os-tc-jesenice/reservation_app/blob/main/poletna-pavza.md")
    lines.append("")

    lines.append("## Recent warning events")
    if summary["warning_events"]:
        for event in summary["warning_events"]:
            obj = getattr(event, "involved_object", None)
            obj_name = getattr(obj, "name", "unknown") if obj else "unknown"
            message = getattr(event, "message", "").replace("\n", " ")[:180]
            lines.append(f"- {fmt_dt(getattr(event, 'last_timestamp', None) or getattr(event, 'event_time', None))} {event.type} {obj_name}: {message}")
    else:
        lines.append("- no warning events in the last 24h")
    lines.append("")

    lines.append("## Collector errors")
    errors = []
    for name, err in k3s["errors"].items():
        if err:
            errors.append(f"k3s/{name}: {err}")
    for name, err in longhorn["errors"].items():
        if err:
            errors.append(f"longhorn/{name}: {err}")
    if errors:
        for err in errors[:30]:
            lines.append(f"- {err}")
        if len(errors) > 30:
            lines.append(f"- ... {len(errors) - 30} more errors omitted")
    else:
        lines.append("- none")

    # ── App data integrity section ──
    if app_data:
        lines.append("")
        lines.append("## App data integrity agent")
        lines.append(f"Period: {app_data['period_start']} → {app_data['period_end']}")
        lines.append(f"Assessments checked: {app_data['total_assessments']}")
        lines.append(f"Blocked dates checked: {app_data['total_blocked']}")
        if app_data["issues"]:
            lines.append(f"Issues found: {len(app_data['issues'])}")
            for issue in app_data["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("✅ No data integrity issues found.")
        lines.append("")

    # ── Documentation reference ──
    lines.append("## Documentation links")
    lines.append("- 📄 [Poletna pavza — navodila za izklop jeseni](https://github.com/os-tc-jesenice/reservation_app/blob/main/poletna-pavza.md)")
    lines.append("")

    return "\n".join(lines)


def run():
    kube, _apis, kube_error = load_kube()
    if kube_error:
        app_data = {"period_start": "N/A", "period_end": "N/A",
                     "total_assessments": 0, "total_blocked": 0, "issues": []}
        body = render_report({}, {}, app_data=app_data, kube_error=kube_error)
        print(body)
        _send_email(settings.BACKUP_EMAIL, "⚠️ Daily report napaka - k3s/Longhorn", body)
        return

    core, apps, batch, custom = kube
    k3s = collect_k3s_agent(core, apps, batch)
    longhorn = collect_longhorn_agent(custom)
    app_data = collect_app_data_agent()
    body = render_report(k3s, longhorn, app_data=app_data)
    print(body)
    _send_email(settings.BACKUP_EMAIL, "🛡️ Daily k3s/Longhorn health report", body)


if __name__ == "__main__":
    run()
