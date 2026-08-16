"""Disk capacity and SMART health, as collected by deploy/disk-health.py.

The portal never touches a raw device. A root systemd timer writes a JSON
report and this module reads it, so the web app stays unprivileged.

That split has a consequence worth stating plainly: **a missing or stale report
is itself a finding**. If the timer stops, the last good numbers would sit there
looking reassuring forever, so staleness is surfaced as a warning rather than
quietly ignored.
"""
import json
import os
from datetime import datetime, timedelta, timezone

DEFAULT_REPORT = "/var/lib/household-portal/disk-health.json"

# Percent used at which a filesystem stops being comfortable.
WARN_PERCENT = 85.0
CRITICAL_PERCENT = 95.0

# The report is written hourly; treat well past that as a stopped collector.
STALE_AFTER = timedelta(hours=6)

OK, WARN, CRITICAL, UNKNOWN = "ok", "warn", "critical", "unknown"
_RANK = {OK: 0, UNKNOWN: 1, WARN: 2, CRITICAL: 3}


def report_path():
    return os.environ.get("DISK_HEALTH_REPORT", DEFAULT_REPORT)


def human_bytes(value):
    if not value:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def worst(statuses):
    return max(statuses, key=lambda s: _RANK.get(s, 1), default=OK)


def _filesystem_status(fs):
    pct = fs.get("use_percent") or 0
    if pct >= CRITICAL_PERCENT:
        return CRITICAL
    if pct >= WARN_PERCENT:
        return WARN
    return OK


def _disk_status(disk):
    if disk.get("smart_ok") is False:
        return CRITICAL
    # Reallocated and pending sectors are the early warning. Any non-zero value
    # deserves a look even while SMART still reports the drive as healthy.
    for field in ("reallocated_sectors", "pending_sectors"):
        if (disk.get(field) or 0) > 0:
            return WARN
    if disk.get("smart_ok") is None:
        return UNKNOWN
    return OK


def load_report(path=None):
    """Parsed report, or None when it has never been written."""
    try:
        with open(path or report_path()) as fh:
            return json.load(fh)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return None


def summary(path=None, now=None):
    """Everything the disks page needs, already classified."""
    now = now or datetime.now(timezone.utc)
    report = load_report(path)

    if report is None:
        return {
            "available": False,
            "status": UNKNOWN,
            "generated_at": None,
            "stale": False,
            "filesystems": [],
            "disks": [],
            "warnings": [
                "No disk report yet. Enable the collector with: "
                "sudo systemctl enable --now disk-health.timer"
            ],
        }

    warnings = []

    generated_at, stale = None, False
    raw_time = report.get("generated_at")
    if raw_time:
        try:
            generated_at = datetime.fromisoformat(raw_time)
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            stale = (now - generated_at) > STALE_AFTER
        except ValueError:
            generated_at = None

    if stale or generated_at is None:
        warnings.append(
            "The disk report is stale — the collector may have stopped. "
            "Check: systemctl status disk-health.timer"
        )

    filesystems = []
    for fs in report.get("filesystems", []):
        entry = dict(fs)
        entry["status"] = _filesystem_status(fs)
        entry["size_h"] = human_bytes(fs.get("size"))
        entry["used_h"] = human_bytes(fs.get("used"))
        entry["avail_h"] = human_bytes(fs.get("avail"))
        filesystems.append(entry)
        if entry["status"] != OK:
            warnings.append(
                f"{fs.get('mount')} is {fs.get('use_percent')}% full "
                f"({entry['avail_h']} free)."
            )

    disks = []
    for disk in report.get("disks", []):
        entry = dict(disk)
        entry["status"] = _disk_status(disk)
        disks.append(entry)
        if disk.get("smart_ok") is False:
            warnings.append(
                f"SMART reports /dev/{disk.get('device')} "
                f"({disk.get('model') or 'unknown model'}) as FAILING. "
                "Replace it and restore from backup."
            )
        else:
            for field, label in (
                ("reallocated_sectors", "reallocated sectors"),
                ("pending_sectors", "pending sectors"),
            ):
                count = disk.get(field) or 0
                if count > 0:
                    warnings.append(
                        f"/dev/{disk.get('device')} has {count} {label}. "
                        "Watch whether the count rises."
                    )

    if not report.get("smartctl_available", True):
        warnings.append("smartctl is not installed, so drive health is unknown.")

    statuses = [f["status"] for f in filesystems] + [d["status"] for d in disks]
    overall = worst(statuses)
    if (stale or generated_at is None) and overall == OK:
        overall = UNKNOWN

    return {
        "available": True,
        "status": overall,
        "generated_at": generated_at,
        "stale": stale,
        "hostname": report.get("hostname"),
        "filesystems": filesystems,
        "disks": disks,
        "warnings": warnings,
    }
