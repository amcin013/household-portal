"""What the machine itself is doing: memory, uptime, load, CPU.

Everything here comes out of /proc and /etc/os-release, all of which are world
readable, so this needs no privilege at all - unlike the disk collector, which
needs root for smartctl and therefore lives in a separate systemd unit.

Deliberately no process list. "Show me the top processes" is a different tool
with a different risk profile: it leaks command lines, which on this box would
include arguments to backup and rsync jobs. This answers "is the machine
healthy", not "what is it running".

Every reader returns None rather than raising. A panel that vanishes when
/proc is not what we expect is better than a home page that 500s - the portal
is meant to survive being run somewhere that is not Palehorse.
"""
import os
import re
import socket
from datetime import timedelta


def _read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except OSError:
        return None


def _meminfo():
    raw = _read("/proc/meminfo")
    if not raw:
        return {}
    out = {}
    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        value = rest.strip().split(" ")[0]
        if value.isdigit():
            out[key] = int(value) * 1024  # kB in the file, bytes out
    return out


def memory():
    info = _meminfo()
    total = info.get("MemTotal")
    if not total:
        return None
    # MemAvailable, not MemFree: the kernel's own estimate of what a new process
    # could actually get. MemFree ignores reclaimable cache and makes a healthy
    # box look 90% full, which is the classic way to misread this number.
    available = info.get("MemAvailable", info.get("MemFree", 0))
    used = total - available
    swap_total = info.get("SwapTotal") or 0
    swap_used = swap_total - (info.get("SwapFree") or 0)
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": round(used / total * 100, 1),
        "swap_total": swap_total,
        "swap_used": swap_used,
        "swap_percent": round(swap_used / swap_total * 100, 1) if swap_total else 0.0,
    }


def uptime_seconds():
    raw = _read("/proc/uptime")
    if not raw:
        return None
    try:
        return float(raw.split()[0])
    except (ValueError, IndexError):
        return None


def uptime_human():
    seconds = uptime_seconds()
    if seconds is None:
        return None
    delta = timedelta(seconds=int(seconds))
    days, rest = delta.days, delta.seconds
    hours, minutes = rest // 3600, (rest % 3600) // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def load():
    raw = _read("/proc/loadavg")
    if not raw:
        return None
    parts = raw.split()
    try:
        one, five, fifteen = (float(p) for p in parts[:3])
    except (ValueError, IndexError):
        return None
    cores = os.cpu_count() or 1
    return {
        "1": one, "5": five, "15": fifteen,
        "cores": cores,
        # Load relative to core count is the only version that means anything:
        # 4.0 is idle on a 32-thread box and on fire on a 2-thread one.
        "percent": round(min(one / cores, 1.0) * 100, 1),
        "busy": one > cores,
    }


def cpu():
    raw = _read("/proc/cpuinfo")
    if not raw:
        return None
    model = re.search(r"^model name\s*:\s*(.+)$", raw, re.M)
    return {
        "model": model.group(1).strip() if model else "Unknown",
        "threads": os.cpu_count() or 1,
    }


def os_release():
    raw = _read("/etc/os-release")
    if not raw:
        return None
    fields = {
        key: (quoted or bare)
        for key, quoted, bare in re.findall(
            r'^([A-Z_]+)=(?:"([^"]*)"|(.*))$', raw, re.M)
    }
    return fields.get("PRETTY_NAME") or fields.get("NAME")


def kernel():
    try:
        info = os.uname()
        return f"{info.sysname} {info.release}"
    except OSError:
        return None


def hostname():
    try:
        return socket.gethostname()
    except OSError:
        return None


def summary():
    """Everything the machine panel needs. Never raises."""
    return {
        "hostname": hostname(),
        "os": os_release(),
        "kernel": kernel(),
        "cpu": cpu(),
        "uptime": uptime_human(),
        "load": load(),
        "memory": memory(),
    }
