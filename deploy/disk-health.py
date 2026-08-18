#!/usr/bin/env python3
"""Collect disk capacity and SMART health, write it where the portal can read it.

Runs as root from a systemd timer. The portal itself runs as an unprivileged
user and must never be given root, so the split is deliberate: this script has
the privileges, the portal only reads the JSON it leaves behind.

    sudo python3 deploy/disk-health.py            # writes the default path
    sudo python3 deploy/disk-health.py --stdout   # print instead, for testing

Standard library only, so it runs with the system python and needs no venv.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

DEFAULT_OUT = "/var/lib/household-portal/disk-health.json"

# Pseudo-filesystems nobody needs a capacity warning about.
SKIP_FSTYPES = {
    "tmpfs", "devtmpfs", "squashfs", "overlay", "efivarfs", "proc", "sysfs",
    "cgroup2", "devpts", "ramfs", "autofs", "fuse.gvfsd-fuse", "fuse.portal",
}


def run(cmd, timeout=30):
    """Return stdout, or None if the command is missing or fails."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def filesystems():
    """Mounted filesystems worth reporting, from findmnt."""
    raw = run(["findmnt", "-J", "-b", "-o", "TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL"])
    if not raw:
        return []

    found = []

    def walk(nodes):
        for node in nodes:
            walk(node.get("children", []))
            fstype = node.get("fstype") or ""
            if fstype in SKIP_FSTYPES or node.get("size") in (None, 0):
                continue
            size = int(node["size"])
            used = int(node.get("used") or 0)
            found.append({
                "mount": node.get("target"),
                "source": node.get("source"),
                "fstype": fstype,
                "size": size,
                "used": used,
                "avail": int(node.get("avail") or 0),
                "use_percent": round(used / size * 100, 1) if size else 0.0,
                # A CIFS/NFS mount is somebody else's disk. Capacity is real,
                # but SMART belongs to the machine hosting it, not this one.
                "network": fstype in {"cifs", "nfs", "nfs4", "smbfs"},
            })

    walk(json.loads(raw).get("filesystems", []))

    # One filesystem can appear under several mount points. This unit runs with
    # PrivateTmp and StateDirectory, so systemd bind-mounts /var/tmp and the
    # state directory into its namespace and findmnt sees them as separate
    # entries -- reporting "/" three times at the same percentage.
    #
    # Deduplicate by the backing source and keep the shallowest mount point,
    # which is the real one rather than a bind of it.
    # The bind shows up as "/dev/sda2[/var/lib/household-portal]", so the
    # subpath has to come off before comparing or every bind looks like its
    # own device and the deduplication above does nothing.
    def backing(source):
        return re.sub(r"\[.*\]$", "", source or "")

    by_source = {}
    for fs in found:
        key = backing(fs["source"]) or fs["mount"]
        current = by_source.get(key)
        if current is None or len(fs["mount"]) < len(current["mount"]):
            by_source[key] = fs

    return sorted(by_source.values(), key=lambda f: -f["use_percent"])


def block_devices():
    raw = run(["lsblk", "-J", "-d", "-o", "NAME,SIZE,MODEL,TYPE"])
    if not raw:
        return []
    return [
        d for d in json.loads(raw).get("blockdevices", [])
        if d.get("type") == "disk" and not d["name"].startswith(("loop", "zram"))
    ]


def _attr(text, name):
    """Pull a SMART attribute's raw value out of `smartctl -A` output."""
    match = re.search(rf"^\s*\d+\s+{name}\S*\s+.*?(\d+)\s*$", text, re.M)
    return int(match.group(1)) if match else None


def smart(device):
    """SMART health for one device. Returns None when unavailable."""
    path = f"/dev/{device}"
    health = run(["smartctl", "-H", path])
    if health is None:
        return None

    passed = None
    if re.search(r"(PASSED|OK)\b", health):
        passed = True
    elif re.search(r"(FAILED|FAILING)", health, re.I):
        passed = False

    info = {"smart_ok": passed}

    attrs = run(["smartctl", "-A", path]) or ""
    # The two that actually predict failure. A non-zero and rising count here
    # is the warning worth acting on -- long before the drive stops working.
    info["reallocated_sectors"] = _attr(attrs, "Reallocated_Sector")
    info["pending_sectors"] = _attr(attrs, "Current_Pending_Sector")
    info["power_on_hours"] = _attr(attrs, "Power_On_Hours")

    temp = re.search(r"Temperature_Celsius\s+.*?(\d+)(?:\s|$)", attrs)
    info["temperature_c"] = int(temp.group(1)) if temp else None
    return info


def collect():
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hostname": os.uname().nodename,
        "smartctl_available": shutil.which("smartctl") is not None,
        "filesystems": filesystems(),
        "disks": [],
    }

    for dev in block_devices():
        entry = {
            "device": dev["name"],
            "model": (dev.get("model") or "").strip() or None,
            "size": dev.get("size"),
        }
        entry.update(smart(dev["name"]) or {"smart_ok": None})
        report["disks"].append(entry)

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.environ.get("DISK_HEALTH_REPORT", DEFAULT_OUT))
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args()

    report = collect()

    if args.stdout:
        json.dump(report, sys.stdout, indent=2)
        print()
        return 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # Write atomically so the portal never reads a half-written file.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(args.out), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(report, fh, indent=2)
    os.chmod(tmp, 0o644)  # the portal user only ever needs to read it
    os.replace(tmp, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
