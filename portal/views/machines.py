"""Virtual machines: see them, and press the power button.

Every action is a POST from a plain form, so the page works with JavaScript
switched off - which is the baseline the rest of the portal holds to and is
doubly right here, because the one time you need to restart Home Assistant
may well be from a phone on a bad connection.
"""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import login_required

from ..auth import admin_required
from ..services import machines as vm

bp = Blueprint("machines", __name__, url_prefix="/machines")


@bp.route("/")
@login_required
def index():
    rows, error = ([], "") if not vm.enabled() else vm.domains(
        force=request.args.get("refresh") == "1"
    )
    return render_template(
        "machines/index.html",
        domains=[{**row, "actions": vm.actions_for(row)} for row in rows],
        error=error,
        enabled=vm.enabled(),
        installed=vm.available(),
        uri=vm.uri(),
        controllable=vm.controllable(),
    )


@bp.route("/<name>")
@login_required
def detail(name):
    domain, error = vm.find(name)
    if domain is None and not error:
        abort(404)
    return render_template(
        "machines/detail.html",
        # The row macro reads its buttons off the domain, so they have to be
        # attached here too - not only on the listing.
        domain={**domain, "actions": vm.actions_for(domain)} if domain else None,
        info=vm.details(name) if domain else None,
        error=error,
        name=name,
    )


@bp.route("/<name>/confirm/<action>")
@login_required
def confirm(name, action):
    """A real page for the one action that can corrupt a filesystem.

    A JavaScript confirm() would be shorter and would vanish for anyone
    browsing without it, which is exactly the person this guard is for.
    """
    spec = vm.ACTIONS.get(action)
    if spec is None or not spec.get("confirm"):
        return redirect(url_for("machines.detail", name=name))
    domain, _ = vm.find(name)
    if domain is None:
        abort(404)
    return render_template("machines/confirm.html", domain=domain,
                           action=action, spec=spec)


@bp.route("/<name>/action", methods=["POST"])
@login_required
def action(name):
    requested = request.form.get("action", "")
    spec = vm.ACTIONS.get(requested)

    # Send anything that needs confirming to the confirmation page rather than
    # refusing it, so the button on the listing is one click away from working.
    if spec and spec.get("confirm") and request.form.get("confirm") != "yes":
        return redirect(url_for("machines.confirm", name=name, action=requested))

    ok, message = vm.act(name, requested,
                         confirmed=request.form.get("confirm") == "yes")
    flash(message, "success" if ok else "error")

    back = request.form.get("back")
    if back == "detail":
        return redirect(url_for("machines.detail", name=name))
    return redirect(url_for("machines.index"))


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    """Admin-only: this decides what the portal is allowed to switch off."""
    from ..extensions import db
    from ..models import Setting

    if request.method == "POST":
        Setting.set("vm_enabled", "1" if request.form.get("enabled") == "on" else "0")
        Setting.set("vm_uri", (request.form.get("uri") or "").strip() or vm.DEFAULT_URI)
        for key in ("vm_controllable", "vm_protected"):
            Setting.set(key, (request.form.get(key) or "").strip())
        db.session.commit()
        vm._cache["value"] = None
        flash("Virtual machine settings saved.", "success")
        return redirect(url_for("machines.settings"))

    rows, error = (vm.domains(force=True) if vm.enabled() else ([], ""))
    return render_template(
        "machines/settings.html",
        settings=Setting.all_as_dict(),
        default_uri=vm.DEFAULT_URI,
        installed=vm.available(),
        found=rows,
        error=error,
    )
