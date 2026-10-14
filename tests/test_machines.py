"""VM control.

The thing worth testing here is not the happy path - it is the guards. This
feature can switch off Home Assistant and the box the portal is running in,
so every refusal below is a test, and `_run` is faked throughout: a test suite
must never be one bad patch away from issuing `virsh destroy` for real.
"""
import pytest

from portal.models import Setting
from portal.services import machines as vm
from tests.conftest import csrf

DOMSTATS = """\
Domain: 'torrentbox'
  state.state=1
  state.reason=1
  cpu.time=12345000000000
  balloon.current=2097152
  balloon.maximum=4194304
  balloon.rss=2300000
  vcpu.current=2
  vcpu.maximum=4

Domain: 'home-assistant'
  state.state=5
  state.reason=0

Domain: 'pacs'
  state.state=1
  vcpu.current=8
"""


@pytest.fixture
def virsh(monkeypatch):
    """A fake hypervisor. Records every call so refusals can be proved."""
    calls = []

    def fake_run(args, timeout=vm.TIMEOUT):
        calls.append(list(args))
        if args[0] == "domstats":
            return True, DOMSTATS, ""
        if args[0] == "dominfo":
            return True, ("Name:           torrentbox\n"
                          "UUID:           abc-123\n"
                          "OS Type:        hvm\n"
                          "State:          running\n"
                          "Persistent:     yes\n"
                          "Autostart:      enable\n"), ""
        if args[0] == "domblklist":
            return True, "file  disk  vda  /var/lib/libvirt/images/tb.qcow2\n", ""
        if args[0] == "domifaddr":
            return True, "vnet0  52:54:00:aa:bb:cc  ipv4  192.168.50.21/24\n", ""
        return True, "", ""

    monkeypatch.setattr(vm, "_run", fake_run)
    monkeypatch.setattr(vm, "available", lambda: True)
    vm._cache["value"] = None
    yield calls
    vm._cache["value"] = None


@pytest.fixture
def configured(app, virsh):
    Setting.set("vm_enabled", "1")
    Setting.set("vm_controllable", "torrentbox, home-assistant")
    Setting.set("vm_protected", "home-assistant")
    from portal.extensions import db
    db.session.commit()
    vm._cache["value"] = None
    return virsh


# --- reading ---------------------------------------------------------------
def test_domstats_parses_state_memory_and_cpus(configured):
    rows, error = vm.domains(force=True)
    assert error == ""
    by_name = {r["name"]: r for r in rows}

    tb = by_name["torrentbox"]
    assert tb["state"] == "running" and tb["running"] is True
    assert tb["vcpus"] == 2
    assert tb["memory"] == 2097152 * 1024      # KiB in, bytes out
    assert tb["cpu_seconds"] == pytest.approx(12345.0)

    # An inactive domain reports nothing but its state, and must not be
    # dressed up with zeroes that look like real readings.
    ha = by_name["home-assistant"]
    assert ha["state"] == "off" and ha["running"] is False
    assert ha["memory"] is None and ha["vcpus"] is None


def test_controllable_machines_sort_first(configured):
    rows, _ = vm.domains(force=True)
    assert [r["name"] for r in rows] == ["home-assistant", "torrentbox", "pacs"]


def test_an_unreachable_hypervisor_is_an_error_not_a_crash(app, monkeypatch):
    monkeypatch.setattr(vm, "available", lambda: True)
    monkeypatch.setattr(vm, "_run",
                        lambda args, timeout=None: (False, "", "Cannot recv data"))
    vm._cache["value"] = None
    rows, error = vm.domains(force=True)
    assert rows == [] and "Cannot recv data" in error


def test_missing_virsh_is_reported_rather_than_raised(app, monkeypatch):
    monkeypatch.setattr(vm, "available", lambda: False)
    vm._cache["value"] = None
    rows, error = vm.domains(force=True)
    assert rows == [] and "not installed" in error


# --- the guards ------------------------------------------------------------
def test_a_machine_not_on_the_list_cannot_be_touched(configured):
    ok, message = vm.act("pacs", "shutdown")
    assert ok is False and "read-only" in message
    assert ["shutdown", "pacs"] not in configured


def test_a_protected_machine_can_be_started_but_not_stopped(configured):
    ok, message = vm.act("home-assistant", "shutdown")
    assert ok is False and "protected" in message
    assert ["shutdown", "home-assistant"] not in configured

    ok, _ = vm.act("home-assistant", "start")
    assert ok is True
    assert ["start", "home-assistant"] in configured


def test_force_off_does_nothing_without_confirmation(configured):
    ok, message = vm.act("torrentbox", "forceoff")
    assert ok is False and "confirming" in message
    assert ["destroy", "torrentbox"] not in configured

    ok, _ = vm.act("torrentbox", "forceoff", confirmed=True)
    assert ok is True
    assert ["destroy", "torrentbox"] in configured


def test_an_unknown_action_is_refused(configured):
    ok, message = vm.act("torrentbox", "undefine")
    assert ok is False and "not something" in message
    assert not any("undefine" in c for c in configured)


def test_an_unknown_machine_is_refused(configured):
    ok, message = vm.act("nope", "start")
    assert ok is False and "no machine" in message.lower()


def test_offered_actions_match_the_state(configured):
    rows = {r["name"]: r for r in vm.domains(force=True)[0]}
    running = [a["key"] for a in vm.actions_for(rows["torrentbox"])]
    assert running == ["shutdown", "reboot", "forceoff"]
    assert [a["key"] for a in vm.actions_for(rows["pacs"])] == []  # not controllable

    # Protected and off: start is the only thing left.
    assert [a["key"] for a in vm.actions_for(rows["home-assistant"])] == ["start"]


def test_action_invalidates_the_cache(configured):
    vm.domains()
    vm.act("torrentbox", "shutdown")
    assert vm._cache["value"] is None


# --- pages -----------------------------------------------------------------
def test_page_says_how_to_switch_it_on_when_it_is_off(auth_client):
    page = auth_client.get("/machines/").get_data(as_text=True)
    assert "Switched off" in page


def test_page_lists_machines_with_their_buttons(auth_client, configured):
    page = auth_client.get("/machines/").get_data(as_text=True)
    assert "torrentbox" in page and "home-assistant" in page
    assert "Shut down" in page
    # The uncontrollable one is listed, but with no way to act on it.
    assert "read-only" in page


def test_detail_shows_address_and_disks(auth_client, configured):
    page = auth_client.get("/machines/torrentbox").get_data(as_text=True)
    assert "192.168.50.21" in page
    assert "tb.qcow2" in page


def test_force_off_from_a_button_goes_to_the_confirm_page(auth_client, configured, app):
    app.config["CSRF_IN_TESTS"] = True
    token = csrf(auth_client, "/machines/")
    response = auth_client.post(
        "/machines/torrentbox/action",
        data={"action": "forceoff", "_csrf_token": token},
    )
    assert response.status_code == 302
    assert "/confirm/forceoff" in response.headers["Location"]
    assert ["destroy", "torrentbox"] not in configured


def test_an_action_without_the_csrf_token_is_rejected(auth_client, configured, app):
    app.config["CSRF_IN_TESTS"] = True
    response = auth_client.post("/machines/torrentbox/action",
                                data={"action": "shutdown"})
    assert response.status_code == 400
    assert ["shutdown", "torrentbox"] not in configured


def test_settings_page_is_admin_only(client, app, configured):
    from portal.extensions import db
    from portal.models import User

    member = User(email="member@example.com", role="member")
    db.session.add(member)
    db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = str(member.id)
        session["_fresh"] = True

    assert client.get("/machines/settings").status_code in (302, 403)


# --- home page -------------------------------------------------------------
def test_panel_is_hidden_until_it_is_configured(auth_client, app):
    from portal.models import User
    from portal.modules import save_layout

    save_layout(User.query.first(), ["machines"], ["machines"])
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "card vms" not in page


def test_panel_shows_the_named_machines_only(auth_client, app, configured):
    from portal.models import User
    from portal.modules import save_layout

    save_layout(User.query.first(), ["machines"], ["machines"])
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "card vms" in page
    assert "torrentbox" in page
    assert "pacs" not in page


def test_panel_offers_one_action_not_three(auth_client, app, configured):
    """Force off must not be one click away from the front page."""
    from portal.models import User
    from portal.modules import save_layout

    save_layout(User.query.first(), ["machines"], ["machines"])
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    panel = page[page.index("card vms"):]
    panel = panel[:panel.index("</section>")]
    assert "Shut down" in panel
    assert "Force off" not in panel
    assert "Reboot" not in panel


def test_panel_is_off_by_default(auth_client, configured):
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "card vms" not in page
