"""Disk health reporting.

The cases that matter are the unhappy ones: no report, a stale report, and a
drive that is failing. A storage page that looks reassuring when the collector
has died is worse than no page at all.
"""
import json
from datetime import datetime, timedelta, timezone

from portal.services import disks


def write_report(tmp_path, **overrides):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hostname": "testbox",
        "smartctl_available": True,
        "filesystems": [
            {
                "mount": "/", "source": "/dev/sda2", "fstype": "ext4",
                "size": 100_000_000_000, "used": 50_000_000_000,
                "avail": 50_000_000_000, "use_percent": 50.0, "network": False,
            }
        ],
        "disks": [
            {
                "device": "sda", "model": "TEST SSD", "size": "119.2G",
                "smart_ok": True, "reallocated_sectors": 0,
                "pending_sectors": 0, "power_on_hours": 100,
                "temperature_c": 30,
            }
        ],
    }
    report.update(overrides)
    path = tmp_path / "disk-health.json"
    path.write_text(json.dumps(report))
    return str(path)


def test_missing_report_is_unknown_not_ok(tmp_path):
    result = disks.summary(path=str(tmp_path / "nope.json"))
    assert result["available"] is False
    assert result["status"] == disks.UNKNOWN
    assert result["warnings"]


def test_healthy_report_is_ok(tmp_path):
    result = disks.summary(path=write_report(tmp_path))
    assert result["status"] == disks.OK
    assert result["warnings"] == []
    assert result["filesystems"][0]["avail_h"] == "46.6 GB"


def test_full_filesystem_warns(tmp_path):
    path = write_report(tmp_path, filesystems=[{
        "mount": "/media/Expansion", "source": "/dev/sde2", "fstype": "exfat",
        "size": 100, "used": 90, "avail": 10, "use_percent": 90.0,
        "network": False,
    }])
    result = disks.summary(path=path)
    assert result["status"] == disks.WARN
    assert "90.0% full" in result["warnings"][0]


def test_full_filesystem_becomes_critical(tmp_path):
    path = write_report(tmp_path, filesystems=[{
        "mount": "/", "source": "/dev/sda2", "fstype": "ext4",
        "size": 100, "used": 97, "avail": 3, "use_percent": 97.0,
        "network": False,
    }])
    assert disks.summary(path=path)["status"] == disks.CRITICAL


def test_failing_smart_is_critical(tmp_path):
    path = write_report(tmp_path, disks=[{
        "device": "sdb", "model": "OLD DISK", "size": "465G",
        "smart_ok": False, "reallocated_sectors": 0, "pending_sectors": 0,
    }])
    result = disks.summary(path=path)
    assert result["status"] == disks.CRITICAL
    assert "FAILING" in result["warnings"][0]


def test_reallocated_sectors_warn_even_when_smart_passes(tmp_path):
    """The early warning: SMART still says PASSED but sectors are going bad."""
    path = write_report(tmp_path, disks=[{
        "device": "sdc", "model": "WD", "size": "931G",
        "smart_ok": True, "reallocated_sectors": 8, "pending_sectors": 0,
    }])
    result = disks.summary(path=path)
    assert result["status"] == disks.WARN
    assert "8 reallocated sectors" in result["warnings"][0]


def test_stale_report_is_flagged(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    result = disks.summary(path=write_report(tmp_path, generated_at=old))
    assert result["stale"] is True
    assert result["status"] == disks.UNKNOWN
    assert any("stale" in w for w in result["warnings"])


def test_worst_status_wins():
    assert disks.worst([disks.OK, disks.WARN, disks.OK]) == disks.WARN
    assert disks.worst([disks.WARN, disks.CRITICAL]) == disks.CRITICAL
    assert disks.worst([]) == disks.OK


def test_disks_page_renders(auth_client):
    response = auth_client.get("/system/disks")
    assert response.status_code == 200
    assert b"Storage" in response.data


def test_disks_page_requires_login(client):
    response = client.get("/system/disks")
    assert response.status_code in (302, 401)
