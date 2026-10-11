"""The machine panel's data source.

Everything here reads /proc, which means it is the one service that behaves
differently depending on where the portal runs. The contract that matters is
that it degrades rather than raises: a home page must not 500 because the
portal was started somewhere that is not Linux.
"""
from portal.services import host


def test_summary_never_raises_and_has_every_key():
    info = host.summary()
    for key in ("hostname", "os", "kernel", "cpu", "uptime", "load", "memory"):
        assert key in info


def test_memory_uses_available_not_free(tmp_path, monkeypatch):
    """MemFree ignores reclaimable cache and makes a healthy box look full."""
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       1000000 kB\n"
        "MemFree:          50000 kB\n"
        "MemAvailable:    800000 kB\n"
        "SwapTotal:       200000 kB\n"
        "SwapFree:        150000 kB\n"
    )
    real_read = host._read
    monkeypatch.setattr(host, "_read",
                        lambda p: meminfo.read_text() if p == "/proc/meminfo" else real_read(p))

    mem = host.memory()
    assert mem["available"] == 800000 * 1024
    assert mem["used"] == 200000 * 1024      # total - available, not total - free
    assert mem["percent"] == 20.0
    assert mem["swap_used"] == 50000 * 1024
    assert mem["swap_percent"] == 25.0


def test_memory_returns_none_when_proc_is_unreadable(monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: None)
    assert host.memory() is None
    assert host.uptime_human() is None
    assert host.load() is None
    assert host.cpu() is None


def test_summary_survives_a_box_with_no_proc(monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: None)
    info = host.summary()
    assert info["memory"] is None
    assert info["uptime"] is None


def test_load_is_scaled_by_core_count(monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: "4.00 2.00 1.00 1/100 999")
    monkeypatch.setattr(host.os, "cpu_count", lambda: 8)
    load = host.load()
    assert load["1"] == 4.0
    assert load["cores"] == 8
    assert load["percent"] == 50.0
    assert load["busy"] is False


def test_load_over_core_count_is_busy(monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: "9.00 2.00 1.00 1/100 999")
    monkeypatch.setattr(host.os, "cpu_count", lambda: 8)
    load = host.load()
    assert load["busy"] is True
    assert load["percent"] == 100.0  # clamped, not 112%


def test_uptime_formats_by_magnitude(monkeypatch):
    for seconds, expected in [
        ("90.0 0", "1m"),
        ("3700.0 0", "1h 1m"),
        ("200000.0 0", "2d 7h 33m"),
    ]:
        monkeypatch.setattr(host, "_read", lambda p, s=seconds: s)
        assert host.uptime_human() == expected


def test_os_release_prefers_pretty_name(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: 'NAME="Arch"\nPRETTY_NAME="EndeavourOS"\n')
    assert host.os_release() == "EndeavourOS"


def test_os_release_handles_unquoted_values(monkeypatch):
    monkeypatch.setattr(host, "_read", lambda p: "NAME=Arch\nID=arch\n")
    assert host.os_release() == "Arch"


def test_machine_panel_renders_when_switched_on(auth_client, app):
    """Server status is off by default - it is a server-admin readout, and on a
    household front page it pushed the weather and the bills below it. It still
    has to render correctly for anyone who turns it on."""
    from portal.models import User
    from portal.modules import save_layout

    save_layout(User.query.first(), ["machine"], ["machine"])
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "card machine" in page


def test_machine_panel_is_not_on_by_default(auth_client):
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "card machine" not in page
