"""Virtual machines, the way Cockpit does it: libvirt, over virsh.

Cockpit's machines page is a web front end to libvirt. This is the same idea
with the same back end, so a VM started here and a VM started in Cockpit are
the same operation - there is no second source of truth to drift.

Why virsh and not libvirt-python: libvirt-python has to be compiled against
libvirt-dev, which would make installing the portal a build. virsh is already
on any box that runs libvirt, it speaks remote URIs natively, and it is a
stable interface. The cost is parsing text, which is handled below.

**The portal usually is not on the hypervisor.** It runs in a guest, so the
normal setup here is a remote connection - `qemu+ssh://user@hypervisor/system`
- and the portal user needs a key the hypervisor accepts. See README.

What this deliberately cannot do
--------------------------------
Define, undefine, edit XML, delete storage, or revert snapshots. Everything
here is a power button: start, shut down, reboot, force off, autostart. The
destructive half of libvirt stays in virsh and Cockpit, where it belongs,
because this is a household portal that someone else may be using in an
emergency and a mis-click should never cost a disk image.

Three guards sit in front of even that much:

* an allowlist - actions are refused on any domain not named in settings, so
  a hypervisor full of VMs exposes exactly the two he asked for;
* a protected list - domains that may be started but never stopped, which is
  how the portal avoids being talked into killing the VM it is running in;
* force-off asks for confirmation, because it is the one action that can
  corrupt a filesystem.
"""
import os
import re
import shutil
import subprocess
import time

# virsh talking to a remote hypervisor over ssh can hang on a dead host. Every
# call is bounded so a sulking hypervisor costs one slow page, not a worker.
TIMEOUT = 12
ACTION_TIMEOUT = 25

# How long a listing is reused. Over ssh every read costs a connection, and
# the home page would otherwise pay for one on every load. Pressing a button
# clears the cache, so the page you land on afterwards is never stale - this
# only bounds how long an change made elsewhere takes to show up.
CACHE_SECONDS = 10

DEFAULT_URI = "qemu:///system"

# libvirt's numeric domain states, and what a person would call them.
STATES = {
    "0": ("unknown", "Unknown"),
    "1": ("running", "Running"),
    "2": ("blocked", "Blocked"),
    "3": ("paused", "Paused"),
    "4": ("shutdown", "Shutting down"),
    "5": ("off", "Off"),
    "6": ("crashed", "Crashed"),
    "7": ("suspended", "Suspended"),
}

# action -> (virsh arguments, what it does to the machine)
#   "stop" actions are refused on protected domains.
ACTIONS = {
    "start":     {"argv": ["start"],              "kind": "start",
                  "label": "Start", "done": "starting"},
    "shutdown":  {"argv": ["shutdown"],           "kind": "stop",
                  "label": "Shut down", "done": "shutting down"},
    "reboot":    {"argv": ["reboot"],             "kind": "stop",
                  "label": "Reboot", "done": "rebooting"},
    "forceoff":  {"argv": ["destroy"],            "kind": "stop",
                  "label": "Force off", "done": "forced off", "confirm": True},
    "autostart": {"argv": ["autostart"],          "kind": "config",
                  "label": "Start with the host", "done": "set to start with the host"},
    "noautostart": {"argv": ["autostart", "--disable"], "kind": "config",
                    "label": "Do not start with the host",
                    "done": "no longer starts with the host"},
}

# Which actions make sense given where the machine is now. Offering Start on a
# running VM is how you get a confusing error instead of a disabled button.
BY_STATE = {
    "running":   ["shutdown", "reboot", "forceoff"],
    "blocked":   ["shutdown", "reboot", "forceoff"],
    "paused":    ["start", "forceoff"],
    "shutdown":  ["forceoff"],
    "off":       ["start"],
    "crashed":   ["start", "forceoff"],
    "suspended": ["start", "forceoff"],
    "unknown":   [],
}

_cache = {"at": 0.0, "uri": None, "value": None}


# --- settings -------------------------------------------------------------
def _setting(key, default=""):
    """Settings, but safe to call with no database behind it.

    The service is imported by the dashboard builder, which runs before
    anything has proven there is a working session.
    """
    try:
        from ..models import Setting
        return Setting.get(key, default) or default
    except Exception:
        return default


def enabled():
    return _setting("vm_enabled", "0") == "1"


def uri():
    return _setting("vm_uri", DEFAULT_URI) or DEFAULT_URI


def _names(key):
    raw = _setting(key, "")
    return [n.strip() for n in re.split(r"[,\n]", raw) if n.strip()]


def controllable():
    """Domains the portal is allowed to act on. Empty means none."""
    return _names("vm_controllable")


def protected():
    """Domains that may be started but never stopped."""
    return _names("vm_protected")


def available():
    """Is virsh even here? A missing binary is a setup problem, not an error."""
    return shutil.which("virsh") is not None


# --- running virsh --------------------------------------------------------
def _env():
    env = dict(os.environ)
    # systemd gives the unit no HOME, and ssh needs one to find its key and
    # known_hosts. Without this a remote URI fails with a bare "Permission
    # denied" that looks like a libvirt problem and is not.
    env.setdefault("HOME", os.path.expanduser("~"))
    env.setdefault("LC_ALL", "C")  # parseable output, whatever the locale
    return env


def _run(args, timeout=TIMEOUT):
    """Run virsh. Returns (ok, stdout, error-for-a-human).

    Never raises and never uses a shell: every argument is passed as its own
    item, so a domain name can hold whatever characters libvirt allows.
    """
    if not available():
        return False, "", "virsh is not installed on this machine."

    try:
        done = subprocess.run(
            ["virsh", "--quiet", "--connect", uri(), *args],
            capture_output=True, text=True, timeout=timeout, env=_env(),
        )
    except subprocess.TimeoutExpired:
        return False, "", f"The hypervisor did not answer within {timeout}s."
    except OSError as exc:
        return False, "", f"Could not run virsh: {exc}"

    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        return False, "", (detail[-1] if detail else "virsh failed.")
    return True, done.stdout, ""


# --- reading ---------------------------------------------------------------
def _parse_domstats(text):
    """`virsh domstats --list-all` for every domain, in one round trip.

    Output is blocks of `Domain: 'name'` followed by indented `key=value`
    lines. Inactive domains get a block with only the state in it.
    """
    domains, current = [], None
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        head = re.match(r"^Domain:\s*'(.*)'$", line.strip())
        if head:
            current = {"name": head.group(1), "stats": {}}
            domains.append(current)
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.strip().partition("=")
        current["stats"][key] = value
    return domains


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _shape(name, stats):
    state_key, state_label = STATES.get(stats.get("state.state"), STATES["0"])

    # balloon.* is in KiB. balloon.rss is what the VM's process actually holds
    # on the host; balloon.current is what the guest has been given. For "is
    # this VM using its memory" the guest's own view is the useful one.
    current = _as_int(stats.get("balloon.current"))
    maximum = _as_int(stats.get("balloon.maximum"))
    rss = _as_int(stats.get("balloon.rss"))

    return {
        "name": name,
        "state": state_key,
        "state_label": state_label,
        "running": state_key in ("running", "blocked"),
        "vcpus": _as_int(stats.get("vcpu.current")) or _as_int(stats.get("vcpu.maximum")),
        "memory": (current * 1024) if current else None,
        "memory_max": (maximum * 1024) if maximum else None,
        "memory_host": (rss * 1024) if rss else None,
        "cpu_seconds": (_as_int(stats.get("cpu.time")) or 0) / 1e9 or None,
        "controllable": name in controllable(),
        "protected": name in protected(),
    }


def domains(force=False):
    """Every domain on the hypervisor, newest state, cheapest way.

    Returns (list, error). An error and an empty list is the shape of "the
    hypervisor is unreachable"; an empty list and no error means it answered
    and has nothing defined.
    """
    now = time.time()
    if (not force and _cache["value"] is not None
            and _cache["uri"] == uri() and now - _cache["at"] < CACHE_SECONDS):
        return _cache["value"]

    ok, out, err = _run(["domstats", "--list-all"])
    if ok:
        rows = [_shape(d["name"], d["stats"]) for d in _parse_domstats(out)]
    else:
        # domstats arrived in libvirt 1.2.8 and --list-all later still. On an
        # older host fall back to the listing that has always existed, which
        # costs the per-VM numbers but keeps the power buttons working.
        ok, out, err2 = _run(["list", "--all", "--name"])
        if not ok:
            result = ([], err or err2)
            _cache.update(at=now, uri=uri(), value=result)
            return result
        rows = []
        for name in (line.strip() for line in out.splitlines()):
            if not name:
                continue
            state_ok, state_out, _ = _run(["domstate", name])
            label = state_out.strip() if state_ok else ""
            key = {"running": "running", "shut off": "off", "paused": "paused",
                   "in shutdown": "shutdown", "crashed": "crashed",
                   "pmsuspended": "suspended"}.get(label, "unknown")
            rows.append(_shape(name, {"state.state": {
                v[0]: k for k, v in STATES.items()}.get(key, "0")}))

    rows.sort(key=lambda d: (not d["controllable"], d["name"].lower()))
    result = (rows, "")
    _cache.update(at=now, uri=uri(), value=result)
    return result


def find(name):
    rows, err = domains()
    for row in rows:
        if row["name"] == name:
            return row, err
    return None, err


def details(name):
    """The extra reads only the detail page needs: autostart, disks, addresses.

    Each one is allowed to fail on its own. A guest with no agent has no IP
    address to report and that is normal, not an error worth showing.
    """
    info = {"autostart": None, "persistent": None, "uuid": None,
            "os": None, "disks": [], "addresses": [], "xml_error": ""}

    ok, out, err = _run(["dominfo", name])
    if not ok:
        info["xml_error"] = err
        return info

    for line in out.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "autostart":
            info["autostart"] = value == "enable"
        elif key == "persistent":
            info["persistent"] = value == "yes"
        elif key == "uuid":
            info["uuid"] = value
        elif key == "os type":
            info["os"] = value

    ok, out, _ = _run(["domblklist", name, "--details"])
    if ok:
        for line in out.splitlines():
            parts = line.split()
            # type device target source
            if len(parts) >= 4 and parts[0] in ("file", "block", "network", "volume"):
                info["disks"].append({"target": parts[2], "source": parts[3],
                                      "device": parts[1]})

    # Leases first: it is the hypervisor's own DHCP record and needs nothing
    # inside the guest. The agent knows more but is usually not installed.
    for source in ("lease", "agent"):
        ok, out, _ = _run(["domifaddr", name, "--source", source])
        if not ok:
            continue
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and "/" in parts[3]:
                info["addresses"].append({"interface": parts[0], "mac": parts[1],
                                          "address": parts[3].split("/")[0]})
        if info["addresses"]:
            break

    return info


# --- acting ----------------------------------------------------------------
def actions_for(domain):
    """What this person can actually press on this machine, in order."""
    if not domain["controllable"]:
        return []
    allowed = BY_STATE.get(domain["state"], [])
    if domain["protected"]:
        allowed = [a for a in allowed if ACTIONS[a]["kind"] != "stop"]
    return [{"key": a, **ACTIONS[a]} for a in allowed]


def act(name, action, confirmed=False):
    """Do one thing to one machine. Returns (ok, message).

    The guards run in the order a reader would ask them: is this a real
    action, is that a real machine, am I allowed to touch it, am I allowed to
    stop it, and did you mean it.
    """
    spec = ACTIONS.get(action)
    if spec is None:
        return False, "That is not something the portal can do."

    domain, err = find(name)
    if domain is None:
        return False, err or f"There is no machine called “{name}” here."

    if not domain["controllable"]:
        return False, (f"“{name}” is read-only. Add it to the controllable list "
                       f"in Settings → Virtual machines first.")

    if spec["kind"] == "stop" and domain["protected"]:
        return False, (f"“{name}” is protected, so the portal will not stop it. "
                       f"Use virsh or Cockpit on the hypervisor.")

    if spec.get("confirm") and not confirmed:
        return False, "Forcing a machine off needs confirming."

    ok, _, err = _run([*spec["argv"], name], timeout=ACTION_TIMEOUT)
    _cache["value"] = None  # whatever it did, the cached listing is now a lie
    if not ok:
        return False, err or f"Could not {spec['label'].lower()} “{name}”."
    return True, f"{name} is {spec['done']}."


def summary():
    """What the home-page panel needs: the controllable machines, and why not."""
    if not enabled():
        return None
    rows, err = domains()
    named = controllable()
    if named:
        rows = [r for r in rows if r["name"] in named]
    return {"domains": rows, "error": err, "uri": uri(),
            "available": available(), "configured": bool(named)}
